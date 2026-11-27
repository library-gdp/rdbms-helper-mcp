#!/usr/bin/env python3
"""Extract the shapes, tables, connectors and images of a .pptx as JSON.

Usage:
    python3 extract_pptx.py INPUT.pptx [--slides 3,5-7] [--media-dir DIR]

Legacy binary .ppt is not supported; convert it to .pptx (or PDF) first.

Like extract_drawio.py, this only returns structure: each slide's text boxes
(with paragraphs), native tables (rows x cells), connectors (the shape ids
they are glued to and their line-end types) and pictures. Deciding which
shape is a table and what each line means is left to the model.
With --media-dir, embedded pictures are copied there so an ERD pasted as an
image can be looked at.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
EMU_PER_PT = 12700


def _q(tag: str) -> str:
    prefix, name = tag.split(":")
    return f"{{{NS[prefix]}}}{name}"


def _paragraphs(el: ET.Element) -> list[str]:
    out = []
    for para in el.iter(_q("a:p")):
        text = "".join(t.text or "" for t in para.iter(_q("a:t"))).strip()
        if text:
            out.append(text)
    return out


def _geometry(el: ET.Element) -> dict | None:
    xfrm = el.find(".//a:xfrm", NS)
    if xfrm is None:
        xfrm = el.find(".//p:xfrm", NS)
    if xfrm is None:
        return None
    off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    return {
        "x": round(int(off.get("x", 0)) / EMU_PER_PT, 1),
        "y": round(int(off.get("y", 0)) / EMU_PER_PT, 1),
        "width": round(int(ext.get("cx", 0)) / EMU_PER_PT, 1),
        "height": round(int(ext.get("cy", 0)) / EMU_PER_PT, 1),
        "flip_h": xfrm.get("flipH") == "1",
        "flip_v": xfrm.get("flipV") == "1",
    }


def _cnv(el: ET.Element) -> ET.Element | None:
    return el.find("./*/p:cNvPr", NS)


def walk(container: ET.Element, rels: dict[str, str], group: str | None, out: dict) -> None:
    for el in container:
        tag = el.tag
        cnv = _cnv(el)
        sid = cnv.get("id") if cnv is not None else None
        name = cnv.get("name") if cnv is not None else None
        if tag == _q("p:sp"):
            geom = el.find("p:spPr/a:prstGeom", NS)
            out["shapes"].append({
                "id": sid, "name": name, "group": group,
                "preset": geom.get("prst") if geom is not None else None,
                "paragraphs": _paragraphs(el),
                "geometry": _geometry(el),
            })
        elif tag == _q("p:cxnSp"):
            props = el.find("p:nvCxnSpPr/p:cNvCxnSpPr", NS)
            st = props.find("a:stCxn", NS) if props is not None else None
            en = props.find("a:endCxn", NS) if props is not None else None
            ln = el.find("p:spPr/a:ln", NS)
            head = ln.find("a:headEnd", NS) if ln is not None else None
            tail = ln.find("a:tailEnd", NS) if ln is not None else None
            dash = ln.find("a:prstDash", NS) if ln is not None else None
            out["connectors"].append({
                "id": sid, "name": name, "group": group,
                "start_shape": st.get("id") if st is not None else None,
                "end_shape": en.get("id") if en is not None else None,
                "head_end": head.get("type") if head is not None else None,
                "tail_end": tail.get("type") if tail is not None else None,
                "dashed": dash is not None and dash.get("val") not in (None, "solid"),
                "geometry": _geometry(el),
            })
        elif tag == _q("p:graphicFrame"):
            tbl = el.find(".//a:tbl", NS)
            if tbl is not None:
                rows = [[" ".join(_paragraphs(tc)) for tc in tr.findall("a:tc", NS)]
                        for tr in tbl.findall("a:tr", NS)]
                out["tables"].append({"id": sid, "name": name, "group": group,
                                      "rows": rows, "geometry": _geometry(el)})
            else:
                out["other"].append({"id": sid, "name": name, "kind": "graphicFrame",
                                     "paragraphs": _paragraphs(el)})
        elif tag == _q("p:pic"):
            blip = el.find(".//a:blip", NS)
            rid = blip.get(_q("r:embed")) if blip is not None else None
            out["pictures"].append({"id": sid, "name": name, "group": group,
                                    "media": rels.get(rid), "geometry": _geometry(el)})
        elif tag == _q("p:grpSp"):
            walk(el, rels, sid, out)


def slide_rels(z: zipfile.ZipFile, slide_path: str) -> dict[str, str]:
    rel_path = posixpath.join(posixpath.dirname(slide_path), "_rels", posixpath.basename(slide_path) + ".rels")
    if rel_path not in z.namelist():
        return {}
    root = ET.fromstring(z.read(rel_path))
    base = posixpath.dirname(slide_path)
    return {r.get("Id"): posixpath.normpath(posixpath.join(base, r.get("Target", "")))
            for r in root.findall("rel:Relationship", NS)}


def slide_order(z: zipfile.ZipFile) -> list[str]:
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    rels = slide_rels(z, "ppt/presentation.xml")
    ids = pres.findall("p:sldIdLst/p:sldId", NS)
    return [rels[s.get(_q("r:id"))] for s in ids if s.get(_q("r:id")) in rels]


def parse_selection(spec: str | None, total: int) -> list[int]:
    if not spec:
        return list(range(1, total + 1))
    out: list[int] = []
    for part in spec.split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not m:
            raise ValueError(f"bad --slides value {part!r}; use e.g. 3,5-7")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        out.extend(n for n in range(a, b + 1) if 1 <= n <= total)
    return sorted(set(out))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("--slides", help="1-based slide numbers, e.g. 3,5-7 (default: all)")
    p.add_argument("--media-dir", help="copy embedded pictures of the selected slides here")
    args = p.parse_args(argv)
    try:
        with zipfile.ZipFile(args.input) as z:
            order = slide_order(z)
            slides = []
            for n in parse_selection(args.slides, len(order)):
                path = order[n - 1]
                rels = slide_rels(z, path)
                tree = ET.fromstring(z.read(path))
                out = {"number": n, "shapes": [], "tables": [], "connectors": [], "pictures": [], "other": []}
                sp_tree = tree.find("p:cSld/p:spTree", NS)
                if sp_tree is not None:
                    walk(sp_tree, rels, None, out)
                if args.media_dir:
                    media_dir = Path(args.media_dir)
                    media_dir.mkdir(parents=True, exist_ok=True)
                    for pic in out["pictures"]:
                        if pic["media"] and pic["media"] in z.namelist():
                            dest = media_dir / f"slide{n}-{posixpath.basename(pic['media'])}"
                            dest.write_bytes(z.read(pic["media"]))
                            pic["extracted_to"] = str(dest)
                slides.append(out)
    except zipfile.BadZipFile:
        print("error: not a .pptx (zip) file; legacy .ppt must be converted to .pptx or PDF first", file=sys.stderr)
        return 2
    except (OSError, KeyError, ValueError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "file": args.input,
        "slides": slides,
        "units": "points",
        "connector_note": "head_end is drawn at start_shape, tail_end at end_shape. PowerPoint has no crow's-foot ends; cardinality is usually written as text (1, N, 0..1) near the line.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
