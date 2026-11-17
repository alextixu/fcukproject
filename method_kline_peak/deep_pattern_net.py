"""
DeepCandlestickProtoNet: 深度 K 線卷積注意力對比原型網路
以深度學習為基礎的 K 線型態辨識系統核心模型

架構特性:
1. 結構化時序張量: (B, T=6, D=10) 捕捉每根 K 棒的微觀無量綱幾何與量能動態
2. 多尺度膨脹 1D-CNN: 同時擷取單棒形態 (十字星/鎚子線)、雙棒 (吞噬/孕線)、三棒 (晨星/黃昏之星)
3. 時序多頭自注意力機制 (Temporal Self-Attention): 捕捉 11 日窗格跨天期高低點支撐阻力拓撲
4. 監督式對比學習 (SupCon): 在超球面流形上主動拉近真反轉形態、推遠假突破陷阱
5. 可解釋性原型頭 (ProtoNet): 學習 K 個經典技術分析形態原型向量 (雙重頂/頭肩頂/反轉鎚等)
"""

from __future__ import annotations
import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiScaleConv1D(nn.Module):
    """多尺度膨脹 1D 卷積塊：提取局部單棒與多棒形態特徵"""
    def __init__(self, in_dim: int = 10, hidden_dim: int = 64):
        super().__init__()
        # 1-bar micro-geometry (kernel=1)
        self.conv1 = nn.Sequential(
            nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=1),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.GELU()
        )
        # 2-bar & 3-bar local combinations (kernel=3, padding=1)
        self.conv3 = nn.Sequential(
            nn.Conv1d(in_dim, hidden_dim // 2, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.GELU()
        )
        # Dilated convolution for wider wave context (kernel=3, dilation=2, padding=2)
        self.conv_dilated = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=2, dilation=2),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU()
        )
        self.proj = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, D, T]
        c1 = self.conv1(x)
        c3 = self.conv3(x)
        cat = torch.cat([c1, c3], dim=1) # [B, hidden_dim, T]
        out = self.conv_dilated(cat)
        out = self.proj(out)
        return out # [B, hidden_dim, T]


class TemporalAttention(nn.Module):
    """時序多頭自注意力機制：捕捉窗格內多日拓撲關係 (如頸線、前高支撐阻力)"""
    def __init__(self, d_model: int = 64, n_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.mha = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.ln1 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model)
        )
        self.ln2 = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [B, T, d_model]
        attn_out, attn_weights = self.mha(x, x, x)
        x = self.ln1(x + attn_out)
        ffn_out = self.ffn(x)
        x = self.ln2(x + ffn_out)
        return x, attn_weights # [B, T, d_model], [B, n_heads, T, T]


class CandlestickProtoNet(nn.Module):
    """統一的端到端深度 K 線型態辨識與原型度量網絡"""
    def __init__(
        self,
        in_dim: int = 10,
        seq_len: int = 6,
        hidden_dim: int = 64,
        latent_dim: int = 32,
        n_classes: int = 3,
        n_prototypes_per_class: int = 8,
        temperature: float = 0.15,
        dropout: float = 0.1
    ):
        super().__init__()
        self.in_dim = in_dim
        self.seq_len = seq_len
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.n_classes = n_classes
        self.n_proto = n_prototypes_per_class
        self.temperature = temperature

        # 1. 卷積前端
        self.conv = MultiScaleConv1D(in_dim, hidden_dim)

        # 2. 時序自注意力
        self.attn = TemporalAttention(hidden_dim, n_heads=4, dropout=dropout)

        # 3. 時序池化
        # Concat(Max, Mean, Last)
        self.pool_proj = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout)
        )

        # 4. 超球面投影頭
        self.proj_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, latent_dim)
        )

        # 5. 可學習形態原型庫: [n_classes, n_proto, latent_dim]
        # 初始在單位超球面上均勻分佈
        init_proto = torch.randn(n_classes, n_prototypes_per_class, latent_dim)
        init_proto = F.normalize(init_proto, p=2, dim=-1)
        self.prototypes = nn.Parameter(init_proto)

        # 輔助分類頭 (直接映射)
        self.classifier = nn.Linear(hidden_dim, n_classes)

    def extract_features(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        x: [B, T, D]
        returns:
            h: [B, hidden_dim]
            z: [B, latent_dim] (L2 normalized)
            attn_weights: [B, heads, T, T]
        """
        B, T, D = x.shape
        x_conv = x.transpose(1, 2) # [B, D, T]
        h_conv = self.conv(x_conv) # [B, hidden_dim, T]
        h_seq = h_conv.transpose(1, 2) # [B, T, hidden_dim]

        h_attn, attn_w = self.attn(h_seq) # [B, T, hidden_dim]

        # Multi-scale pooling
        p_max = torch.max(h_attn, dim=1)[0]
        p_mean = torch.mean(h_attn, dim=1)
        p_last = h_attn[:, -1, :]
        p_cat = torch.cat([p_max, p_mean, p_last], dim=-1)

        h = self.pool_proj(p_cat) # [B, hidden_dim]
        z_raw = self.proj_head(h) # [B, latent_dim]
        z = F.normalize(z_raw, p=2, dim=-1) # L2 normalize onto S^{d-1}

        return h, z, attn_w

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        h, z, attn_w = self.extract_features(x)

        # 計算與各類形態原型的餘弦相似度
        # proto: [n_classes, n_proto, latent_dim] -> normalized
        norm_proto = F.normalize(self.prototypes, p=2, dim=-1)

        # z: [B, latent_dim]
        # sim: z @ proto.T -> [B, n_classes, n_proto]
        sims = torch.einsum("bd,ckd->bck", z, norm_proto)

        # 每個類別取最相似原型的得分 (Softmax 聚合)
        proto_logits = torch.max(sims, dim=-1)[0] / self.temperature # [B, n_classes]

        direct_logits = self.classifier(h) # [B, n_classes]

        # 融合原型得分與直出 Logits
        final_logits = 0.7 * proto_logits + 0.3 * direct_logits
        probs = F.softmax(final_logits, dim=-1)

        return {
            "logits": final_logits,
            "proto_logits": proto_logits,
            "probs": probs,
            "z": z,
            "sims": sims,
            "attn_weights": attn_w
        }

    def get_nearest_prototype_info(self, x: torch.Tensor) -> list[dict]:
        """推論時取得每個樣本最匹配的原型編號與相似度 (可解釋性)"""
        self.eval()
        with torch.no_grad():
            out = self.forward(x)
            sims = out["sims"].cpu().numpy() # [B, n_classes, n_proto]
            probs = out["probs"].cpu().numpy()
            preds = np.argmax(probs, axis=-1)

            results = []
            for i in range(len(x)):
                c = preds[i]
                best_k = int(np.argmax(sims[i, c]))
                best_sim = float(sims[i, c, best_k])
                results.append({
                    "pred_class": int(c),
                    "prob": float(probs[i, c]),
                    "prototype_id": best_k,
                    "similarity": best_sim
                })
            return results


class SupervisedContrastiveLoss(nn.Module):
    """
    Supervised Contrastive Loss (SupCon)
    強制同類別的反轉形態在超球面上緊密聚集，並推開不同類別（尤其是反轉 vs 假突破）
    """
    def __init__(self, temperature: float = 0.1):
        super().__init__()
        self.temperature = temperature

    def forward(self, features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        # features: [B, d] normalized
        # labels: [B]
        device = features.device
        B = features.shape[0]
        if B <= 1:
            return torch.tensor(0.0, device=device)

        labels = labels.contiguous().view(-1, 1)
        mask = torch.eq(labels, labels.T).float().to(device)

        # 計算成對餘弦相似度矩陣
        sim_matrix = torch.div(torch.matmul(features, features.T), self.temperature)

        # 遮蔽自身對比項
        logits_max, _ = torch.max(sim_matrix, dim=1, keepdim=True)
        logits = sim_matrix - logits_max.detach()

        logits_mask = torch.scatter(
            torch.ones_like(mask),
            1,
            torch.arange(B).view(-1, 1).to(device),
            0
        )
        mask = mask * logits_mask

        # 指數項
        exp_logits = torch.exp(logits) * logits_mask
        log_prob = logits - torch.log(exp_logits.sum(1, keepdim=True) + 1e-8)

        # 計算正樣本對平均對數機率
        mean_log_prob_pos = (mask * log_prob).sum(1) / (mask.sum(1) + 1e-8)
        loss = -mean_log_prob_pos.mean()
        return loss
