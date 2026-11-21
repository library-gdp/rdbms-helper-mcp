"""Unit tests for src/skills/erd-to-dbgraph/scripts.

Run: python3 -m unittest discover -s src/tests/erd-to-dbgraph -v
"""

from __future__ import annotations

import base64
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPTS = HERE.parents[1] / "skills" / "erd-to-dbgraph" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dbgraph_write  # noqa: E402
import extract_drawio  # noqa: E402
import extract_pptx  # noqa: E402
import parse_mermaid  # noqa: E402


def run(main, argv: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


VALID = {
    "format_version": 1,
    "graph_name": "company",
    "source": {"format": "text", "files": [], "description": None},
    "vertices": [
        {"id": "employee", "table": "employee", "columns": [
            {"name": "id", "type": "bigint", "primary_key": True},
            {"name": "department_id", "type": "bigint", "nullable": False},
        ]},
        {"id": "department", "table": "department", "columns": [
            {"name": "id", "type": "bigint", "primary_key": True},
        ]},
    ],
    "edges": [
        {"source": "employee", "target": "department",
         "source_columns": ["department_id"], "target_columns": ["id"],
         "cardinality": {"source": {"min": 0, "max": "many"},
                         "target": {"min": 1, "max": "one"}}},
    ],
}


class WriterTests(unittest.TestCase):
    def test_normalizes_valid_graph(self):
        graph, errors = dbgraph_write.normalize_graph(copy.deepcopy(VALID))
        self.assertEqual(errors, [])
        self.assertEqual([v["id"] for v in graph["vertices"]], ["department", "employee"])
        edge = graph["edges"][0]
        self.assertEqual(edge["id"], "employee.department_id->department.id")
        self.assertEqual(edge["relationship"], "many-to-one")
        self.assertEqual(edge["assumptions"], [])
        self.assertIsNone(edge["identifying"])
        emp = graph["vertices"][1]
        self.assertTrue(emp["columns"][1]["foreign_key"])  # marked from edge
        self.assertFalse(emp["columns"][0]["nullable"])  # PK -> not null
        self.assertIsNone(emp["schema"])

    def test_reports_actionable_errors(self):
        bad = copy.deepcopy(VALID)
        bad["graph_name"] = "회사 DB"
        bad["edges"][0]["target"] = "dept"
        bad["edges"][0]["cardinality"]["source"]["max"] = "N"
        bad["vertices"][0]["columns"].append({"name": "id"})
        bad["vertices"][0]["colour"] = "red"
        graph, errors = dbgraph_write.normalize_graph(bad)
        self.assertIsNone(graph)
        text = "\n".join(errors)
        self.assertIn("$.graph_name", text)
        self.assertIn('$.edges[0].target: unknown vertex "dept"', text)
        self.assertIn("$.edges[0].cardinality.source.max", text)
        self.assertIn("duplicate column", text)
        self.assertIn("$.vertices[0].colour: unknown field", text)

    def test_missing_fk_column_and_length_mismatch(self):
        bad = copy.deepcopy(VALID)
        bad["edges"][0]["source_columns"] = ["dept_id"]
        _, errors = dbgraph_write.normalize_graph(bad)
        self.assertTrue(any('column "dept_id" does not exist in "employee"' in e for e in errors))
        bad["edges"][0]["source_columns"] = ["department_id", "id"]
        _, errors = dbgraph_write.normalize_graph(bad)
        self.assertTrue(any("must have the same length" in e for e in errors))

    def test_schema_qualified_id_and_duplicate_generated_ids(self):
        g = copy.deepcopy(VALID)
        g["vertices"][0].update({"schema": "hr", "id": "hr.employee"})
        g["edges"] = [
            {"source": "hr.employee", "target": "department",
             "cardinality": {"source": {"min": None, "max": "many"}, "target": {"min": None, "max": "one"}}},
            {"source": "hr.employee", "target": "department",
             "cardinality": {"source": {"min": None, "max": "many"}, "target": {"min": None, "max": "one"}}},
        ]
        graph, errors = dbgraph_write.normalize_graph(g)
        self.assertEqual(errors, [])
        self.assertEqual([e["id"] for e in graph["edges"]],
                         ["hr.employee->department", "hr.employee->department#2"])
        wrong = copy.deepcopy(VALID)
        wrong["vertices"][0]["schema"] = "hr"
        _, errors = dbgraph_write.normalize_graph(wrong)
        self.assertTrue(any('must be "hr.employee"' in e for e in errors))

    def test_cli_writes_refuses_overwrite_and_checks(self):
        with tempfile.TemporaryDirectory() as root:
            draft = json.dumps(VALID)
            code, out, _ = run(dbgraph_write.main, ["-", "--root", root, "--check"], draft)
            self.assertEqual(code, 0)
            self.assertFalse(json.loads(out)["written"])
            target = Path(root) / ".rdb-info" / "dbgraph" / "company.json"
            self.assertFalse(target.exists())

            code, out, _ = run(dbgraph_write.main, ["-", "--root", root], draft)
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(out)["written"])
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["graph_name"], "company")
            # Saved output is a fixed point of normalization.
            again, errors = dbgraph_write.normalize_graph(copy.deepcopy(saved))
            self.assertEqual(errors, [])
            self.assertEqual(again, saved)

            code, _, err = run(dbgraph_write.main, ["-", "--root", root], draft)
            self.assertEqual(code, 3)
            self.assertIn("--overwrite", err)
            code, _, _ = run(dbgraph_write.main, ["-", "--root", root, "--overwrite"], draft)
            self.assertEqual(code, 0)

            code, _, err = run(dbgraph_write.main, ["-", "--root", root], "{not json")
            self.assertEqual(code, 2)
            code, _, err = run(dbgraph_write.main, ["-", "--root", root], json.dumps({"graph_name": "x"}))
            self.assertEqual(code, 1)


class MermaidTests(unittest.TestCase):
    def setUp(self):
        self.draft = parse_mermaid.to_draft(
            parse_mermaid.parse((FIXTURES / "company.mmd").read_text(encoding="utf-8")),
            None, "company.mmd")
        self.edges = {(e["source"], e["target"], e["label"]): e for e in self.draft["edges"]}

    def test_entities_and_columns(self):
        self.assertEqual(self.draft["graph_name"], "company")  # from front matter title
        self.assertEqual(self.draft["notes"], [])
        tables = {v["table"]: v for v in self.draft["vertices"]}
        self.assertEqual(set(tables), {"DEPARTMENT", "EMPLOYEE", "PROJECT", "EMPLOYEE_PROJECT", "PARKING_PERMIT"})
        self.assertEqual(tables["EMPLOYEE"]["description"], "직원")
        name = tables["DEPARTMENT"]["columns"][1]
        self.assertEqual((name["type"], name["unique"], name["description"]), ("varchar(100)", True, "부서명"))
        ep = tables["EMPLOYEE_PROJECT"]["columns"]
        self.assertTrue(all(c["primary_key"] and c["foreign_key"] for c in ep))
        self.assertEqual(tables["PROJECT"]["columns"][0]["name"], "id")  # one-line entity body

    def test_direction_and_cardinality(self):
        e = self.edges[("EMPLOYEE", "DEPARTMENT", "has")]  # DEPARTMENT ||--o{ EMPLOYEE
        self.assertEqual(e["cardinality"], {"source": {"min": 0, "max": "many"},
                                            "target": {"min": 1, "max": "one"}})
        self.assertTrue(e["identifying"])
        self.assertEqual((e["source_columns"], e["target_columns"]), (["department_id"], ["id"]))

        self_ref = self.edges[("EMPLOYEE", "EMPLOYEE", "manages")]  # }o..o|
        self.assertFalse(self_ref["identifying"])
        self.assertEqual(self_ref["source_columns"], [])

        one_one = self.edges[("PARKING_PERMIT", "EMPLOYEE", "holds")]  # 1:1, FK by name
        self.assertEqual(one_one["source_columns"], ["employee_id"])
        self.assertEqual(one_one["cardinality"]["source"], {"min": 0, "max": "one"})

    def test_aliases_markdown_and_unparsed(self):
        text = "# doc\n```mermaid\nerDiagram\n  A one or more optionally to zero or one B : rel\n  A {\n    int id PK\n    ???\n  }\n  B\n  bogus line here !\n```\n"
        parsed = parse_mermaid.parse(text)
        e = parsed["edges"][0]
        self.assertEqual((e["source"], e["target"]), ("A", "B"))
        self.assertEqual(e["cardinality"]["source"], {"min": 1, "max": "many"})
        self.assertFalse(e["identifying"])
        self.assertEqual(len(parsed["notes"]), 2)

    def test_draft_is_accepted_by_writer(self):
        _, errors = dbgraph_write.normalize_graph(self.draft)
        self.assertEqual(errors, [])

    def test_rejects_non_er_input(self):
        with self.assertRaises(ValueError):
            parse_mermaid.parse("flowchart LR\n A --> B\n")


class DrawioTests(unittest.TestCase):
    def check(self, data: dict):
        page = data["pages"][0]
        shapes = {s["id"]: s for s in page["shapes"]}
        self.assertEqual(shapes["t1"]["shape"], "table")
        self.assertEqual(shapes["t1r1c2"]["text"], "id bigint")
        self.assertEqual(shapes["t1r1c2"]["top_level"], "t1")
        self.assertEqual(shapes["t2"]["text"], "orders\nid bigint PK\ncustomer_id bigint FK")
        self.assertNotIn("e1l", shapes)
        (edge,) = page["edges"]
        self.assertEqual((edge["source_top_level"], edge["target_top_level"]), ("t2", "t1"))
        self.assertEqual(edge["start_marker"], {"marker": "ERzeroToMany", "min": 0, "max": "many"})
        self.assertEqual(edge["end_marker"], {"marker": "ERmandOne", "min": 1, "max": "one"})
        self.assertTrue(edge["dashed"])
        self.assertEqual(edge["labels"], ["places"])

    def test_plain(self):
        code, out, err = run(extract_drawio.main, [str(FIXTURES / "shop.drawio")])
        self.assertEqual(code, 0, err)
        self.check(json.loads(out))

    def test_compressed_and_svg(self):
        src = (FIXTURES / "shop.drawio").read_text(encoding="utf-8")
        model = src[src.index("<mxGraphModel>"):src.index("</mxGraphModel>") + len("</mxGraphModel>")]
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        packed = base64.b64encode(comp.compress(quote(model).encode()) + comp.flush()).decode()
        mxfile = f'<mxfile><diagram name="shop" id="p1">{packed}</diagram></mxfile>'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.drawio"
            p.write_text(mxfile, encoding="utf-8")
            code, out, err = run(extract_drawio.main, [str(p)])
            self.assertEqual(code, 0, err)
            self.check(json.loads(out))

            from xml.sax.saxutils import quoteattr
            svg = Path(d) / "c.drawio.svg"
            svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" content={quoteattr(mxfile)}></svg>', encoding="utf-8")
            code, out, err = run(extract_drawio.main, [str(svg), "--page", "shop"])
            self.assertEqual(code, 0, err)
            self.check(json.loads(out))

    def test_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.xml"
            p.write_text("<html/>", encoding="utf-8")
            code, _, err = run(extract_drawio.main, [str(p)])
            self.assertEqual(code, 2)
            self.assertIn("not a draw.io file", err)


P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
REL = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
SLIDE = f"""<p:sld {P}><p:cSld><p:spTree>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="dept"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
 <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1270000" cy="635000"/></a:xfrm><a:prstGeom prst="rect"/></p:spPr>
 <p:txBody><a:p><a:r><a:t>department</a:t></a:r></a:p><a:p><a:r><a:t>id PK</a:t></a:r></a:p></p:txBody></p:sp>
<p:grpSp><p:nvGrpSpPr><p:cNvPr id="10" name="g"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
 <p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="3" name="emp"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
  <p:xfrm><a:off x="2540000" y="0"/><a:ext cx="1270000" cy="635000"/></p:xfrm>
  <a:graphic><a:graphicData><a:tbl>
   <a:tr><a:tc><a:txBody><a:p><a:r><a:t>employee</a:t></a:r></a:p></a:txBody></a:tc></a:tr>
   <a:tr><a:tc><a:txBody><a:p><a:r><a:t>dept_id</a:t></a:r></a:p></a:txBody></a:tc><a:tc><a:txBody><a:p><a:r><a:t>FK</a:t></a:r></a:p></a:txBody></a:tc></a:tr>
  </a:tbl></a:graphicData></a:graphic></p:graphicFrame></p:grpSp>
<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="4" name="line"/><p:cNvCxnSpPr><a:stCxn id="3" idx="1"/><a:endCxn id="2" idx="3"/></p:cNvCxnSpPr><p:nvPr/></p:nvCxnSpPr>
 <p:spPr><a:xfrm flipH="1"><a:off x="1270000" y="317500"/><a:ext cx="1270000" cy="0"/></a:xfrm><a:ln><a:prstDash val="dash"/><a:tailEnd type="triangle"/></a:ln></p:spPr></p:cxnSp>
<p:pic><p:nvPicPr><p:cNvPr id="5" name="img"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId2"/></p:blipFill><p:spPr/></p:pic>
</p:spTree></p:cSld></p:sld>"""


def make_pptx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/presentation.xml", f'<p:presentation {P}><p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>')
        z.writestr("ppt/_rels/presentation.xml.rels", f'<Relationships {REL}><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>')
        z.writestr("ppt/slides/slide1.xml", f"<p:sld {P}><p:cSld><p:spTree/></p:cSld></p:sld>")
        z.writestr("ppt/slides/slide2.xml", SLIDE)
        z.writestr("ppt/slides/_rels/slide2.xml.rels", f'<Relationships {REL}><Relationship Id="rId2" Target="../media/image1.png"/></Relationships>')
        z.writestr("ppt/media/image1.png", b"\x89PNG fake")


class PptxTests(unittest.TestCase):
    def test_extract(self):
        with tempfile.TemporaryDirectory() as d:
            pptx = Path(d) / "erd.pptx"
            make_pptx(pptx)
            media = Path(d) / "media"
            code, out, err = run(extract_pptx.main, [str(pptx), "--slides", "2", "--media-dir", str(media)])
            self.assertEqual(code, 0, err)
            (slide,) = json.loads(out)["slides"]
            self.assertEqual(slide["number"], 2)
            self.assertEqual(slide["shapes"][0]["paragraphs"], ["department", "id PK"])
            self.assertEqual(slide["shapes"][0]["geometry"]["width"], 100.0)
            self.assertEqual(slide["tables"][0]["rows"], [["employee"], ["dept_id", "FK"]])
            self.assertEqual(slide["tables"][0]["group"], "10")
            c = slide["connectors"][0]
            self.assertEqual((c["start_shape"], c["end_shape"], c["tail_end"], c["dashed"]), ("3", "2", "triangle", True))
            self.assertTrue(c["geometry"]["flip_h"])
            pic = slide["pictures"][0]
            self.assertEqual(pic["media"], "ppt/media/image1.png")
            self.assertTrue(Path(pic["extracted_to"]).read_bytes().startswith(b"\x89PNG"))

    def test_rejects_non_zip_and_bad_selection(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "old.ppt"
            p.write_bytes(b"\xd0\xcf\x11\xe0 not a zip")
            code, _, err = run(extract_pptx.main, [str(p)])
            self.assertEqual(code, 2)
            self.assertIn("legacy .ppt", err)
        with self.assertRaises(ValueError):
            extract_pptx.parse_selection("a-b", 3)
        self.assertEqual(extract_pptx.parse_selection("3,1-2,9", 3), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
