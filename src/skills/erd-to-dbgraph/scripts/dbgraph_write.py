#!/usr/bin/env python3
"""Validate, normalize and save a DB graph JSON (format_version 1).

Usage:
    python3 dbgraph_write.py [DRAFT_JSON|-] [--root DIR] [--overwrite] [--check]

Reads a draft graph (file path, or stdin when omitted / "-"), validates it
against references/graph-format.md, normalizes it, and writes it to
{root}/.rdb-info/dbgraph/{graph_name}.json.

Exit codes:
    0  success (written, or valid with --check)
    1  validation failed (errors on stderr, one per line)
    2  bad usage / unreadable input
    3  target file exists and --overwrite was not given
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORMAT_VERSION = 1
OUTPUT_DIR = Path(".rdb-info") / "dbgraph"
GRAPH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SOURCE_FORMATS = {
    "mermaid", "drawio", "pptx", "image", "pdf", "sql-ddl",
    "dbml", "plantuml", "text", "other",
}
MAX_VALUES = {"one", "many"}
MIN_VALUES = {0, 1, None}

TOP_KEYS = {"format_version", "graph_name", "source", "vertices", "edges", "notes"}
SOURCE_KEYS = {"format", "files", "description"}
VERTEX_KEYS = {"id", "table", "schema", "description", "columns"}
COLUMN_KEYS = {
    "name", "type", "nullable", "primary_key", "unique",
    "foreign_key", "default", "description",
}
EDGE_KEYS = {
    "id", "source", "target", "source_columns", "target_columns",
    "cardinality", "relationship", "identifying", "label", "assumptions",
}


class Errors:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, path: str, msg: str) -> None:
        self.items.append(f"{path}: {msg}")

    def __bool__(self) -> bool:
        return bool(self.items)


def _is_str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _opt_str(errors: Errors, path: str, v) -> None:
    if v is not None and not isinstance(v, str):
        errors.add(path, f"must be a string or null, got {type(v).__name__}")


def _bool(errors: Errors, path: str, v, nullable: bool = False) -> None:
    if v is None and nullable:
        return
    if not isinstance(v, bool):
        allowed = "true, false or null" if nullable else "true or false"
        errors.add(path, f"must be {allowed}, got {json.dumps(v)}")


def _str_list(errors: Errors, path: str, v) -> bool:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        errors.add(path, "must be an array of strings")
        return False
    return True


def _unknown_keys(errors: Errors, path: str, obj: dict, allowed: set[str]) -> None:
    for k in sorted(set(obj) - allowed):
        errors.add(f"{path}.{k}", f"unknown field (allowed: {', '.join(sorted(allowed))})")


def normalize_column(errors: Errors, path: str, col) -> dict | None:
    if not isinstance(col, dict):
        errors.add(path, "must be an object")
        return None
    _unknown_keys(errors, path, col, COLUMN_KEYS)
    out = {
        "name": col.get("name"),
        "type": col.get("type"),
        "nullable": col.get("nullable"),
        "primary_key": col.get("primary_key", False),
        "unique": col.get("unique", False),
        "foreign_key": col.get("foreign_key", False),
        "default": col.get("default"),
        "description": col.get("description"),
    }
    if not _is_str(out["name"]):
        errors.add(f"{path}.name", "required non-empty string")
    _opt_str(errors, f"{path}.type", out["type"])
    _bool(errors, f"{path}.nullable", out["nullable"], nullable=True)
    for k in ("primary_key", "unique", "foreign_key"):
        _bool(errors, f"{path}.{k}", out[k])
    _opt_str(errors, f"{path}.default", out["default"])
    _opt_str(errors, f"{path}.description", out["description"])
    if out["primary_key"] is True and out["nullable"] is True:
        errors.add(f"{path}.nullable", "a primary key column cannot be nullable")
    if out["primary_key"] is True and out["nullable"] is None:
        out["nullable"] = False
    return out


def normalize_vertex(errors: Errors, path: str, v) -> dict | None:
    if not isinstance(v, dict):
        errors.add(path, "must be an object")
        return None
    _unknown_keys(errors, path, v, VERTEX_KEYS)
    table = v.get("table")
    schema = v.get("schema")
    if not _is_str(table):
        errors.add(f"{path}.table", "required non-empty string")
        return None
    if schema is not None and not _is_str(schema):
        errors.add(f"{path}.schema", "must be a non-empty string or null")
        schema = None
    expected_id = f"{schema}.{table}" if schema else table
    vid = v.get("id", expected_id)
    if vid != expected_id:
        errors.add(f"{path}.id", f"must be {json.dumps(expected_id)} (\"{{schema}}.{{table}}\" or table), got {json.dumps(vid)}")
    _opt_str(errors, f"{path}.description", v.get("description"))
    cols_in = v.get("columns", [])
    columns = []
    if not isinstance(cols_in, list):
        errors.add(f"{path}.columns", "must be an array")
    else:
        seen: set[str] = set()
        for i, c in enumerate(cols_in):
            nc = normalize_column(errors, f"{path}.columns[{i}]", c)
            if nc is None:
                continue
            if isinstance(nc["name"], str):
                if nc["name"] in seen:
                    errors.add(f"{path}.columns[{i}].name", f"duplicate column {json.dumps(nc['name'])} in table {json.dumps(expected_id)}")
                seen.add(nc["name"])
            columns.append(nc)
    return {
        "id": expected_id,
        "table": table,
        "schema": schema,
        "description": v.get("description"),
        "columns": columns,
    }


def _norm_end(errors: Errors, path: str, end) -> dict:
    if not isinstance(end, dict):
        errors.add(path, 'must be an object like {"min": 0|1|null, "max": "one"|"many"}')
        return {"min": None, "max": None}
    _unknown_keys(errors, path, end, {"min", "max"})
    mn, mx = end.get("min"), end.get("max")
    if isinstance(mn, bool) or mn not in MIN_VALUES:
        errors.add(f"{path}.min", f"must be 0, 1 or null, got {json.dumps(mn)}")
    if mx not in MAX_VALUES:
        errors.add(f"{path}.max", f'must be "one" or "many", got {json.dumps(mx)}; ask the user if the ERD does not show it')
    return {"min": mn, "max": mx}


def normalize_edge(errors: Errors, path: str, e, vertices: dict[str, dict]) -> dict | None:
    if not isinstance(e, dict):
        errors.add(path, "must be an object")
        return None
    _unknown_keys(errors, path, e, EDGE_KEYS)
    src, tgt = e.get("source"), e.get("target")
    for key, vid in (("source", src), ("target", tgt)):
        if not _is_str(vid):
            errors.add(f"{path}.{key}", "required vertex id")
        elif vid not in vertices:
            errors.add(f"{path}.{key}", f"unknown vertex {json.dumps(vid)} (known: {', '.join(sorted(vertices)) or 'none'})")

    scols = e.get("source_columns", [])
    tcols = e.get("target_columns", [])
    ok_s = _str_list(errors, f"{path}.source_columns", scols)
    ok_t = _str_list(errors, f"{path}.target_columns", tcols)
    if ok_s and ok_t and len(scols) != len(tcols):
        errors.add(path, f"source_columns ({len(scols)}) and target_columns ({len(tcols)}) must have the same length; use [] for both when unknown")
    for key, vid, cols, ok in (("source_columns", src, scols, ok_s), ("target_columns", tgt, tcols, ok_t)):
        if ok and vid in vertices:
            names = {c["name"] for c in vertices[vid]["columns"]}
            for c in cols:
                if c not in names:
                    errors.add(f"{path}.{key}", f"column {json.dumps(c)} does not exist in {json.dumps(vid)}")

    card = e.get("cardinality")
    if not isinstance(card, dict):
        errors.add(f"{path}.cardinality", 'required object {"source": {...}, "target": {...}}')
        card = {}
    else:
        _unknown_keys(errors, f"{path}.cardinality", card, {"source", "target"})
    cs = _norm_end(errors, f"{path}.cardinality.source", card.get("source"))
    ct = _norm_end(errors, f"{path}.cardinality.target", card.get("target"))
    relationship = None
    if cs["max"] in MAX_VALUES and ct["max"] in MAX_VALUES:
        relationship = f"{cs['max']}-to-{ct['max']}"

    _bool(errors, f"{path}.identifying", e.get("identifying"), nullable=True)
    label = e.get("label")
    _opt_str(errors, f"{path}.label", label)
    assumptions = e.get("assumptions", [])
    _str_list(errors, f"{path}.assumptions", assumptions)

    eid = e.get("id")
    if eid is not None and not _is_str(eid):
        errors.add(f"{path}.id", "must be a non-empty string or omitted")
        eid = None

    return {
        "id": eid,
        "source": src,
        "target": tgt,
        "source_columns": list(scols) if ok_s else [],
        "target_columns": list(tcols) if ok_t else [],
        "cardinality": {"source": cs, "target": ct},
        "relationship": relationship,
        "identifying": e.get("identifying"),
        "label": label,
        "assumptions": list(assumptions) if isinstance(assumptions, list) else [],
    }


def default_edge_id(e: dict) -> str:
    if e["source_columns"]:
        return f"{e['source']}.{','.join(e['source_columns'])}->{e['target']}.{','.join(e['target_columns'])}"
    base = f"{e['source']}->{e['target']}"
    return f"{base}:{e['label']}" if e.get("label") else base


def normalize_graph(data) -> tuple[dict | None, list[str]]:
    errors = Errors()
    if not isinstance(data, dict):
        return None, ["$: top level must be a JSON object"]
    _unknown_keys(errors, "$", data, TOP_KEYS)

    fv = data.get("format_version", FORMAT_VERSION)
    if fv != FORMAT_VERSION:
        errors.add("$.format_version", f"must be {FORMAT_VERSION}")
    name = data.get("graph_name")
    if not isinstance(name, str) or not GRAPH_NAME_RE.match(name):
        errors.add("$.graph_name", f"must match {GRAPH_NAME_RE.pattern} (database name, used as file name), got {json.dumps(name)}")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.add("$.source", 'required object {"format": ..., "files": [...], "description": ...}')
        source = {}
    else:
        _unknown_keys(errors, "$.source", source, SOURCE_KEYS)
    fmt = source.get("format")
    if fmt not in SOURCE_FORMATS:
        errors.add("$.source.format", f"must be one of {', '.join(sorted(SOURCE_FORMATS))}, got {json.dumps(fmt)}")
    files = source.get("files", [])
    _str_list(errors, "$.source.files", files)
    _opt_str(errors, "$.source.description", source.get("description"))

    notes = data.get("notes", [])
    _str_list(errors, "$.notes", notes)

    vertices: dict[str, dict] = {}
    vin = data.get("vertices")
    if not isinstance(vin, list):
        errors.add("$.vertices", "required array of tables")
        vin = []
    elif not vin:
        errors.add("$.vertices", "must contain at least one table")
    for i, v in enumerate(vin):
        nv = normalize_vertex(errors, f"$.vertices[{i}]", v)
        if nv is None:
            continue
        if nv["id"] in vertices:
            errors.add(f"$.vertices[{i}].id", f"duplicate vertex id {json.dumps(nv['id'])}")
            continue
        vertices[nv["id"]] = nv

    edges: list[dict] = []
    ein = data.get("edges", [])
    if not isinstance(ein, list):
        errors.add("$.edges", "must be an array")
        ein = []
    for i, e in enumerate(ein):
        ne = normalize_edge(errors, f"$.edges[{i}]", e, vertices)
        if ne is not None:
            edges.append(ne)

    if errors:
        return None, errors.items

    # Assign ids: explicit ids first (must be unique), then generated ones.
    used: set[str] = set()
    for i, e in enumerate(edges):
        if e["id"] is not None:
            if e["id"] in used:
                errors.add(f"$.edges[{i}].id", f"duplicate edge id {json.dumps(e['id'])}")
            used.add(e["id"])
    if errors:
        return None, errors.items
    for e in edges:
        if e["id"] is None:
            base = default_edge_id(e)
            eid, n = base, 1
            while eid in used:
                n += 1
                eid = f"{base}#{n}"
            e["id"] = eid
            used.add(eid)

    # Mark FK columns referenced by edges.
    for e in edges:
        for c in e["source_columns"]:
            for col in vertices[e["source"]]["columns"]:
                if col["name"] == c:
                    col["foreign_key"] = True

    graph = {
        "format_version": FORMAT_VERSION,
        "graph_name": name,
        "source": {
            "format": fmt,
            "files": list(files),
            "description": source.get("description"),
        },
        "vertices": [vertices[k] for k in sorted(vertices)],
        "edges": sorted(edges, key=lambda e: e["id"]),
        "notes": list(notes),
    }
    return graph, []


def warnings_for(graph: dict) -> list[str]:
    """Non-fatal findings worth reporting to the user."""
    out = []
    linked = {e["source"] for e in graph["edges"]} | {e["target"] for e in graph["edges"]}
    fk_cols_in_edges = {(e["source"], c) for e in graph["edges"] for c in e["source_columns"]}
    for v in graph["vertices"]:
        if not v["columns"]:
            out.append(f"table {v['id']} has no columns")
        if v["id"] not in linked and len(graph["vertices"]) > 1:
            out.append(f"table {v['id']} has no relationships")
        for c in v["columns"]:
            if c["foreign_key"] and (v["id"], c["name"]) not in fk_cols_in_edges:
                out.append(f"column {v['id']}.{c['name']} is marked FK but no edge uses it")
    for e in graph["edges"]:
        if not e["source_columns"] and e["relationship"] != "many-to-many":
            out.append(f"edge {e['id']} has no FK columns")
    return out


def output_path(root: Path, graph_name: str) -> Path:
    return root / OUTPUT_DIR / f"{graph_name}.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("draft", nargs="?", default="-", help="draft graph JSON file, or - for stdin")
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    p.add_argument("--overwrite", action="store_true", help="replace an existing graph file")
    p.add_argument("--check", action="store_true", help="validate only, do not write")
    args = p.parse_args(argv)

    try:
        text = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read draft JSON: {exc}", file=sys.stderr)
        return 2

    graph, errors = normalize_graph(data)
    if errors:
        print(f"validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    target = output_path(Path(args.root), graph["graph_name"])
    summary = {
        "graph_name": graph["graph_name"],
        "path": str(target),
        "vertices": len(graph["vertices"]),
        "edges": len(graph["edges"]),
        "warnings": warnings_for(graph),
        "written": False,
    }
    if not args.check:
        if target.exists() and not args.overwrite:
            print(f"error: {target} already exists; confirm with the user, then re-run with --overwrite", file=sys.stderr)
            return 3
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(target)
        summary["written"] = True
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
