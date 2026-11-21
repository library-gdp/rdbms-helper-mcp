#!/usr/bin/env python3
"""Extract the raw shapes and connectors of a draw.io diagram as JSON.

Usage:
    python3 extract_drawio.py INPUT [--page NAME_OR_INDEX]

INPUT may be .drawio / .xml (plain or compressed), or .drawio.svg / .svg that
embeds the diagram. (.drawio.png: export it as .drawio or .svg first.)

This does NOT decide what is a table or a column: ERD shapes in draw.io vary
(entity shapes, swimlane tables, HTML tables, plain boxes). It returns every
cell with its text, style, parent, top-level container and geometry, plus each
connector's endpoints and decoded crow's-foot arrow markers, so the model can
build the graph from structured data instead of reading XML.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import zlib
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

# draw.io ER arrow names -> (min, max) of the end they are drawn at.
ER_MARKERS = {
    "ERmandOne": (1, "one"),
    "ERzeroToOne": (0, "one"),
    "ERoneToMany": (1, "many"),
    "ERzeroToMany": (0, "many"),
    "ERone": (None, "one"),
    "ERmany": (None, "many"),
}


def _decompress(data: str) -> str:
    raw = base64.b64decode(data)
    return unquote(zlib.decompress(raw, -15).decode("utf-8"))


def load_mxfile(path: Path) -> ET.Element:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    if root.tag.endswith("svg"):
        content = root.get("content")
        if not content:
            raise ValueError("SVG has no embedded draw.io diagram (missing 'content' attribute)")
        root = ET.fromstring(html.unescape(content) if content.lstrip().startswith("&lt;") else content)
    if root.tag == "mxGraphModel":
        wrapper = ET.Element("mxfile")
        d = ET.SubElement(wrapper, "diagram", {"name": "Page-1", "id": "0"})
        d.append(root)
        return wrapper
    if root.tag != "mxfile":
        raise ValueError(f"not a draw.io file (root element <{root.tag}>)")
    return root


def page_model(diagram: ET.Element) -> ET.Element:
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model
    data = (diagram.text or "").strip()
    if not data:
        raise ValueError(f"page {diagram.get('name')!r} is empty")
    return ET.fromstring(_decompress(data))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    s = re.sub(r"</(?:div|p|tr|li|h\d)>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</t[dh]>", "\t", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [ln.strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def parse_style(style: str | None) -> dict:
    out = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
        else:
            out["shape_name"] = part
    return out


def _marker(name: str | None) -> dict | None:
    if name in ER_MARKERS:
        mn, mx = ER_MARKERS[name]
        return {"marker": name, "min": mn, "max": mx}
    return {"marker": name, "min": None, "max": None} if name and name != "none" else None


def extract_page(diagram: ET.Element) -> dict:
    model = page_model(diagram)
    root = model.find("root")
    if root is None:
        raise ValueError(f"page {diagram.get('name')!r} has no <root>")

    cells: dict[str, dict] = {}
    for el in root:
        # A cell may be wrapped in <object>/<UserObject> carrying label + custom attributes.
        if el.tag in ("object", "UserObject"):
            inner = el.find("mxCell")
            if inner is None:
                continue
            attrs = {k: v for k, v in el.attrib.items() if k not in ("id", "label", "placeholders")}
            cid, label, cell = el.get("id"), el.get("label"), inner
        elif el.tag == "mxCell":
            attrs, cid, label, cell = {}, el.get("id"), el.get("value"), el
        else:
            continue
        geo = cell.find("mxGeometry")
        geometry = None
        if geo is not None and cell.get("vertex") == "1":
            geometry = {k: float(geo.get(k, 0)) for k in ("x", "y", "width", "height")}
        cells[cid] = {
            "id": cid,
            "text": clean_text(label),
            "kind": "edge" if cell.get("edge") == "1" else "vertex" if cell.get("vertex") == "1" else "other",
            "parent": cell.get("parent"),
            "style": parse_style(cell.get("style")),
            "geometry": geometry,
            "source": cell.get("source"),
            "target": cell.get("target"),
            "attributes": attrs,
        }

    layers = {cid for cid, c in cells.items() if c["kind"] == "other"}

    def top_level(cid: str | None) -> str | None:
        seen = set()
        while cid and cid in cells and cells[cid]["parent"] not in layers and cid not in seen:
            seen.add(cid)
            cid = cells[cid]["parent"]
        return cid if cid in cells else None

    shapes, edges = [], []
    for c in cells.values():
        if c["kind"] == "vertex":
            shapes.append({
                "id": c["id"],
                "text": c["text"],
                "parent": None if c["parent"] in layers else c["parent"],
                "top_level": top_level(c["id"]),
                "shape": c["style"].get("shape") or c["style"].get("shape_name"),
                "geometry": c["geometry"],
                "attributes": c["attributes"],
            })
        elif c["kind"] == "edge":
            st = c["style"]
            edges.append({
                "id": c["id"],
                "text": c["text"],
                "source": c["source"],
                "target": c["target"],
                "source_top_level": top_level(c["source"]),
                "target_top_level": top_level(c["target"]),
                "start_marker": _marker(st.get("startArrow")),
                "end_marker": _marker(st.get("endArrow")),
                "dashed": st.get("dashed") == "1",
                "attributes": c["attributes"],
            })
    # Edge labels are child vertices of the edge; attach them to the edge.
    edge_ids = {e["id"] for e in edges}
    labels = [s for s in shapes if s["parent"] in edge_ids]
    for e in edges:
        extra = [s["text"] for s in labels if s["parent"] == e["id"] and s["text"]]
        e["labels"] = ([e["text"]] if e["text"] else []) + extra
        del e["text"]
    shapes = [s for s in shapes if s["parent"] not in edge_ids]
    return {"name": diagram.get("name"), "shapes": shapes, "edges": edges}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("--page", help="page name or 0-based index (default: all pages)")
    args = p.parse_args(argv)
    try:
        mxfile = load_mxfile(Path(args.input))
        diagrams = mxfile.findall("diagram")
        if args.page is not None:
            if args.page.isdigit():
                diagrams = diagrams[int(args.page):int(args.page) + 1]
            else:
                diagrams = [d for d in diagrams if d.get("name") == args.page]
            if not diagrams:
                raise ValueError(f"page {args.page!r} not found")
        pages = [extract_page(d) for d in diagrams]
    except (OSError, ValueError, ET.ParseError, zlib.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"file": args.input, "pages": pages,
                      "marker_note": "start_marker is drawn at the source end and describes the source cell's multiplicity; end_marker likewise for the target."},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
