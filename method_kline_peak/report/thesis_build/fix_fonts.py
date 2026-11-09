"""把 LibreOffice 另存 docx 的樣式字型統一為 Times New Roman / 標楷體,並確保 ZIP 沒有資料夾項目。
用法: python3 fix_fonts.py in.docx out.docx"""
import re, sys, zipfile
src, dst = sys.argv[1:3]
FULL = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="標楷體" w:cs="Times New Roman"/>'
zin = zipfile.ZipFile(src)
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for it in zin.infolist():
        if it.filename.endswith("/"):
            continue
        data = zin.read(it.filename)
        if it.filename == "word/styles.xml":
            x = data.decode("utf8")
            n0 = len(re.findall(r"Liberation|WenQuanYi|FreeSans|DejaVu", x))
            x = re.sub(r'<w:rFonts [^>]*(Liberation|WenQuanYi|FreeSans|DejaVu)[^>]*/>', FULL, x)
            print("styles: replaced", n0, "->", len(re.findall(r"Liberation|WenQuanYi|FreeSans|DejaVu", x)))
            data = x.encode("utf8")
        elif it.filename == "word/settings.xml":
            x = data.decode("utf8")
            if "w:updateFields" not in x:
                # 開啟時更新欄位(目錄、圖目錄、表目錄頁碼);位置在 settings 的子元素中,放在 w:defaultTabStop 之前即可符合順序
                # CT_Settings 順序:… alwaysMergeEmptyNamespace, updateFields, hdrShapeDefaults, footnotePr, endnotePr, compat, docVars, rsids, mathPr, …
                after = ["w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat", "w:docVars", "w:rsids", "m:mathPr",
                         "w:attachedSchema", "w:themeFontLang", "w:clrSchemeMapping", "w:doNotIncludeSubdocsInStats",
                         "w:doNotAutoCompressPictures", "w:forceUpgrade", "w:captions", "w:readModeInkLockDown", "w:smartTagType",
                         "sl:schemaLibrary", "w:shapeDefaults", "w:doNotEmbedSmartTags", "w:decimalSymbol", "w:listSeparator"]
                pos = min([k for k in (x.find("<" + t) for t in after) if k >= 0] or [x.rfind("</w:settings>")])
                x = x[:pos] + '<w:updateFields w:val="true"/>' + x[pos:]
            print("settings updateFields:", "w:updateFields" in x)
            data = x.encode("utf8")
        elif it.filename in ("word/document.xml", "word/footer1.xml", "word/footer2.xml", "word/footer3.xml"):
            x = data.decode("utf8")
            n0 = len(re.findall(r"Liberation|WenQuanYi|FreeSans|DejaVu", x))
            if n0:
                x = re.sub(r'<w:rFonts [^>]*(Liberation|WenQuanYi|FreeSans|DejaVu)[^>]*/>', FULL, x)
                print(it.filename, "replaced", n0)
            if it.filename == "word/document.xml":
                # 分節設定移到段落屬性最後(CT_PPr 的順序:… rPr, sectPr, pPrChange)
                def mv(m):
                    body = m.group(1)
                    sp = re.search(r"<w:sectPr\b.*?</w:sectPr>", body, re.S)
                    if not sp:
                        return m.group(0)
                    rest = body[:sp.start()] + body[sp.end():]
                    return "<w:pPr>" + rest + sp.group(0) + "</w:pPr>"
                x = re.sub(r"<w:pPr>(.*?)</w:pPr>", mv, x, flags=re.S)
                # 頁首 1.5 cm、頁尾 1.75 cm(LibreOffice 在沒有頁首時寫成 0)
                x = re.sub(r'(<w:pgMar\b[^>]*?)w:header="\d+"', r'\1w:header="850"', x)
                x = re.sub(r'(<w:pgMar\b[^>]*?)w:footer="\d+"', r'\1w:footer="992"', x)
                print("pgMar:", re.findall(r"<w:pgMar[^>]*>", x))
            data = x.encode("utf8")
        zout.writestr(it, data)
