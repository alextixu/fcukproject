"""用 LibreOffice(UNO)開 docx → 更新所有索引(目錄 / 圖目錄 / 表目錄)與欄位 → 匯出 PDF,並另存更新後的 docx。
用法: python3 lo_update.py in.docx out.pdf [out_updated.docx]"""
import os, sys, time, subprocess, tempfile, pathlib
sys.path.insert(0, sys.argv[4] if len(sys.argv) > 4 else "")
import uno
from com.sun.star.beans import PropertyValue

def pv(n, v):
    p = PropertyValue(); p.Name = n; p.Value = v; return p

src, pdf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
out_docx = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
prof = tempfile.mkdtemp(prefix="lo_prof_")
env = os.environ.copy(); env["SAL_USE_VCLPLUGIN"] = "svp"
proc = subprocess.Popen(["soffice", f"-env:UserInstallation={pathlib.Path(prof).as_uri()}", "--headless", "--invisible",
                         "--norestore", "--accept=socket,host=127.0.0.1,port=2002;urp;"], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ctx = None
local = uno.getComponentContext()
res = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
for _ in range(60):
    try:
        ctx = res.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(1)
smgr = ctx.ServiceManager
desk = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
doc = desk.loadComponentFromURL(uno.systemPathToFileUrl(src), "_blank", 0, (pv("Hidden", True),))
for _ in range(3):                      # 更新兩次以上:目錄本身占頁數會讓後面頁碼移動
    idx = doc.getDocumentIndexes()
    for i in range(idx.getCount()):
        idx.getByIndex(i).update()
    doc.getTextFields().refresh()
    doc.refresh()
print("indexes:", doc.getDocumentIndexes().getCount())
doc.storeToURL(uno.systemPathToFileUrl(pdf), (pv("FilterName", "writer_pdf_Export"),))
if out_docx:
    doc.storeToURL(uno.systemPathToFileUrl(out_docx), (pv("FilterName", "MS Word 2007 XML"),))
doc.close(True)
try:
    desk.terminate()
except Exception:
    pass
proc.wait(timeout=30)
