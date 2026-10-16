"""Export a Korean pptx to PDF through LibreOffice with Asian/Latin auto-spacing turned off.
LibreOffice adds a gap between Hangul and Latin characters by default ("됐습니다 ." / "1 억");
PowerPoint and Keynote do not, so this keeps the PDF identical to what the pptx shows there.
Usage: python3 export_pdf_ko.py in.pptx out.pdf"""
import os, subprocess, sys, time, uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value
    return p


def fix_text(obj):
    """Turn off Asian/Latin auto-spacing on every paragraph of a shape, table cell or group."""
    if obj.supportsService("com.sun.star.drawing.GroupShape"):
        for i in range(obj.getCount()):
            fix_text(obj.getByIndex(i))
        return
    if obj.supportsService("com.sun.star.drawing.TableShape"):
        model = obj.Model
        for r in range(model.Rows.Count):
            for c in range(model.Columns.Count):
                cell = model.getCellByPosition(c, r)
                cell.setPropertyValue("ParaIsCharacterDistance", False)
                fix_cursor(cell)
                cell.setString(cell.getString())  # force re-layout of the cell text
                cell.setPropertyValue("ParaIsCharacterDistance", False)
        return
    try:
        fix_cursor(obj.Text)
    except Exception:
        pass


def fix_cursor(text):
    cur = text.createTextCursor()
    cur.gotoStart(False)
    cur.gotoEnd(True)
    cur.setPropertyValue("ParaIsCharacterDistance", False)


def main(src, dst):
    port = 2083
    proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                             f"--accept=socket,host=localhost,port={port};urp;"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=localhost,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("LibreOffice did not start")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(src)), "_blank", 0, (prop("Hidden", True),))
        pages = doc.DrawPages
        for i in range(pages.Count):
            page = pages.getByIndex(i)
            for j in range(page.Count):
                fix_text(page.getByIndex(j))
        doc.storeToURL(uno.systemPathToFileUrl(os.path.abspath(dst)), (prop("FilterName", "impress_pdf_Export"),))
        doc.close(True)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    print("saved", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
