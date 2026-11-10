"""造一个最小但合法的 xlsx（两个工作表 / 共享字符串 / 日期单元格 / 数字）。"""
import zipfile
from pathlib import Path

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"

CONTENT_TYPES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""

ROOT_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{NS_R}/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS}" xmlns:r="{NS_R}">
<sheets>
<sheet name="销售数据" sheetId="1" r:id="rId1"/>
<sheet name="区域明细" sheetId="2" r:id="rId2"/>
</sheets>
</workbook>"""

WB_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{NS_R}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="{NS_R}/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="{NS_R}/styles" Target="styles.xml"/>
<Relationship Id="rId4" Type="{NS_R}/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{NS}">
<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy/m/d"/></numFmts>
<fonts count="1"><font><sz val="11"/><name val="等线"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
</styleSheet>"""

STRINGS = ["月份", "销量", "利润", "日期", "1月", "2月", "3月", "区域", "金额", "华北", "华东", "华南"]

SHARED = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="{NS}" count="{len(STRINGS)}" uniqueCount="{len(STRINGS)}">
""" + "".join(f"<si><t>{s}</t></si>" for s in STRINGS) + "</sst>"


def cell(ref, value=None, sid=None, style=None):
    attrs = f' r="{ref}"'
    if style is not None:
        attrs += f' s="{style}"'
    if sid is not None:
        return f'<c{attrs} t="s"><v>{sid}</v></c>'
    return f"<c{attrs}><v>{value}</v></c>"


SHEET1 = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{NS}"><sheetData>
<row r="1">{cell("A1", sid=0)}{cell("B1", sid=1)}{cell("C1", sid=2)}{cell("D1", sid=3)}</row>
<row r="2">{cell("A2", sid=4)}{cell("B2", 120)}{cell("C2", 36)}{cell("D2", 46000, style=1)}</row>
<row r="3">{cell("A3", sid=5)}{cell("B3", 132)}{cell("C3", 41)}{cell("D3", 46031, style=1)}</row>
<row r="4">{cell("A4", sid=6)}{cell("B4", 101)}{cell("C4", 28)}{cell("D4", 46059, style=1)}</row>
</sheetData></worksheet>"""

SHEET2 = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{NS}"><sheetData>
<row r="1">{cell("A1", sid=7)}{cell("B1", sid=8)}</row>
<row r="2">{cell("A2", sid=9)}{cell("B2", 320)}</row>
<row r="3">{cell("A3", sid=10)}{cell("B3", 410)}</row>
<row r="4">{cell("A4", sid=11)}{cell("B4", 280)}</row>
</sheetData></worksheet>"""


def build(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", WB_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/sharedStrings.xml", SHARED)
        z.writestr("xl/worksheets/sheet1.xml", SHEET1)
        z.writestr("xl/worksheets/sheet2.xml", SHEET2)
    return path




def build_big(path, rows=200):
    """200 行的大表，验证截断与渲染。"""
    rows_xml = [f'<row r="1">{cell("A1", sid=3)}{cell("B1", sid=4)}</row>']
    for i in range(rows):
        rows_xml.append(
            f'<row r="{i + 2}">{cell(f"A{i + 2}", sid=0)}{cell(f"B{i + 2}", (i * 7) % 130 + 20)}</row>'
        )
    sheet = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             f'<worksheet xmlns="{NS}"><sheetData>{"".join(rows_xml)}</sheetData></worksheet>')
    wb = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          f'<workbook xmlns="{NS}" xmlns:r="{NS_R}"><sheets>'
          f'<sheet name="明细" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{NS_R}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="{NS_R}/styles" Target="styles.xml"/>
</Relationships>"""
    strings = ["名称", "数量"] + [f"项目{i + 1}" for i in range(rows)]
    shared = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              f'<sst xmlns="{NS}" count="{len(strings)}" uniqueCount="{len(strings)}">'
              + "".join(f"<si><t>{v}</t></si>" for v in strings) + "</sst>")
    path = Path(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return path

if __name__ == "__main__":
    out = build(Path(__file__).parent / "_data" / "销售报表.xlsx")
    print(out, out.stat().st_size)
    big = build_big(Path(__file__).parent / "_data" / "大表.xlsx")
    print(big, big.stat().st_size)
