#!/usr/bin/env python3
"""Parse a Mermaid `erDiagram` into a draft DB graph (format_version 1).

Usage:
    python3 parse_mermaid.py INPUT [--graph-name NAME] [--source-file PATH]

INPUT is a .mmd/.md file (the first ```mermaid erDiagram block is used when
the file is Markdown) or - for stdin. The draft is printed to stdout; save it
with dbgraph_write.py. Lines the parser does not understand are listed in the
draft's "notes" so they can be reviewed instead of silently dropped.

Mermaid carries no nullability or schema information, so those stay null.
FK columns of an edge are inferred by name only when unambiguous, and every
inference is recorded in the edge's "assumptions".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Cardinality tokens: (min, max). Both orientations of each symbol are accepted.
SYMBOLS = {
    "|o": (0, "one"), "o|": (0, "one"),
    "||": (1, "one"),
    "}o": (0, "many"), "o{": (0, "many"),
    "}|": (1, "many"), "|{": (1, "many"),
}
ALIASES = {
    "zero or one": (0, "one"), "one or zero": (0, "one"),
    "only one": (1, "one"), "1": (1, "one"),
    "zero or more": (0, "many"), "zero or many": (0, "many"),
    "many(0)": (0, "many"), "0+": (0, "many"),
    "one or more": (1, "many"), "one or many": (1, "many"),
    "many(1)": (1, "many"), "1+": (1, "many"),
}

NAME = r'(?:"[^"]+"|[A-Za-z_][\w-]*)'
SYM = r"(?:\|o|o\||\|\||\}o|o\{|\}\||\|\{)"
ALIAS = "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True))

REL_SYMBOL_RE = re.compile(
    rf"^(?P<a>{NAME})\s*(?P<ca>{SYM})(?P<line>--|\.\.)(?P<cb>{SYM})\s*(?P<b>{NAME})\s*(?::\s*(?P<label>.*))?$"
)
REL_ALIAS_RE = re.compile(
    rf"^(?P<a>{NAME})\s+(?P<ca>{ALIAS})\s+(?P<line>optionally to|to)\s+(?P<cb>{ALIAS})\s+(?P<b>{NAME})\s*(?::\s*(?P<label>.*))?$",
    re.IGNORECASE,
)
ENTITY_OPEN_RE = re.compile(rf"^(?P<name>{NAME})(?:\s*\[\s*(?P<alias>[^\]]+?)\s*\])?\s*\{{\s*(?P<rest>.*)$")
ENTITY_BARE_RE = re.compile(rf"^(?P<name>{NAME})(?:\s*\[\s*(?P<alias>[^\]]+?)\s*\])?(?::::\S+)?$")
ATTR_RE = re.compile(
    r'^(?P<type>\S+)\s+(?P<name>\*?[^\s",]+)'
    r'(?:\s+(?P<keys>(?:PK|FK|UK)(?:\s*,\s*(?:PK|FK|UK))*))?'
    r'(?:\s+"(?P<comment>[^"]*)")?\s*$'
)
IGNORED_RE = re.compile(r"^(?:direction\s+\w+|style\s|classDef\s|class\s|accTitle|accDescr|title\s)", re.IGNORECASE)


def _unquote(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] == '"' else s


def extract_block(text: str) -> str:
    """Return the erDiagram source, taking it out of a Markdown fence if needed."""
    for block in re.findall(r"```mermaid[^\n]*\n(.*?)```", text, re.DOTALL):
        if re.search(r"^\s*erDiagram\b", block, re.MULTILINE):
            return block
    return text


def parse(text: str) -> dict:
    src = extract_block(text)
    entities: dict[str, dict] = {}
    rels: list[dict] = []
    notes: list[str] = []
    title = None

    lines = src.splitlines()
    # YAML front matter (--- ... ---)
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        j = i + 1
        while j < len(lines) and lines[j].strip() != "---":
            m = re.match(r"^\s*title\s*:\s*(.+?)\s*$", lines[j])
            if m:
                title = _unquote(m.group(1))
            j += 1
        i = j + 1

    seen_header = False
    current: dict | None = None

    def ensure(name: str, alias: str | None = None) -> dict:
        ent = entities.setdefault(name, {"table": name, "description": None, "columns": []})
        if alias:
            ent["description"] = _unquote(alias)
        return ent

    def add_attr(ent: dict, raw: str, lineno: int) -> None:
        m = ATTR_RE.match(raw)
        if not m:
            notes.append(f"line {lineno}: unparsed attribute in {ent['table']}: {raw}")
            return
        keys = {k.strip().upper() for k in (m.group("keys") or "").split(",") if k.strip()}
        ent["columns"].append({
            "name": m.group("name").lstrip("*"),
            "type": m.group("type"),
            "nullable": None,
            "primary_key": "PK" in keys or m.group("name").startswith("*"),
            "unique": "UK" in keys,
            "foreign_key": "FK" in keys,
            "default": None,
            "description": m.group("comment"),
        })

    for lineno, raw_line in enumerate(lines[i:], start=i + 1):
        line = re.sub(r"%%.*$", "", raw_line).strip()
        if not line:
            continue
        if not seen_header:
            if re.match(r"^erDiagram\b", line):
                seen_header = True
                continue
            raise ValueError(f"line {lineno}: expected 'erDiagram', got {raw_line.strip()!r}")

        if current is not None:
            if line.startswith("}"):
                current = None
                continue
            body, closed = (line[:-1].strip(), True) if line.endswith("}") else (line, False)
            if body:
                add_attr(current, body, lineno)
            if closed:
                current = None
            continue

        m = REL_SYMBOL_RE.match(line)
        if m:
            ca, cb = SYMBOLS[m.group("ca")], SYMBOLS[m.group("cb")]
        else:
            m = REL_ALIAS_RE.match(line)
            if m:
                ca, cb = ALIASES[m.group("ca").lower()], ALIASES[m.group("cb").lower()]
        if m:
            a, b = _unquote(m.group("a")), _unquote(m.group("b"))
            ensure(a)
            ensure(b)
            label = m.group("label")
            line_kind = m.group("line").lower()
            rels.append({
                "a": a, "b": b, "ca": ca, "cb": cb,
                "identifying": line_kind == "--" or line_kind == "to",
                "label": _unquote(label) if label and label.strip() else None,
                "lineno": lineno,
            })
            continue

        m = ENTITY_OPEN_RE.match(line)
        if m:
            current = ensure(_unquote(m.group("name")), m.group("alias"))
            rest = m.group("rest").strip()
            if rest.endswith("}"):
                body = rest[:-1].strip()
                if body:
                    add_attr(current, body, lineno)
                current = None
            elif rest:
                add_attr(current, rest, lineno)
            continue

        if IGNORED_RE.match(line):
            continue
        m = ENTITY_BARE_RE.match(line)
        if m:
            ensure(_unquote(m.group("name")), m.group("alias"))
            continue
        notes.append(f"line {lineno}: unparsed line: {raw_line.strip()}")

    if not seen_header:
        raise ValueError("no 'erDiagram' found in input")
    if current is not None:
        notes.append(f"entity {current['table']}: missing closing '}}'")

    edges = [build_edge(r, entities) for r in rels]
    return {"title": title, "entities": entities, "edges": edges, "notes": notes}


def _fk_match(child: dict, parent: dict) -> tuple[list[str], list[str]] | None:
    """Infer child FK -> parent PK by name when exactly one candidate exists."""
    pks = [c["name"] for c in parent["columns"] if c["primary_key"]]
    if len(pks) != 1:
        return None
    pk = pks[0]
    p = parent["table"].lower()
    wanted = {f"{p}_{pk}".lower(), f"{p}{pk}".lower(), f"{p}_id"}
    cols = child["columns"]
    fk_cols = [c for c in cols if c["foreign_key"]]
    pool = fk_cols or cols
    hits = [c["name"] for c in pool if c["name"].lower() in wanted]
    if not hits and fk_cols:
        hits = [c["name"] for c in fk_cols if c["name"].lower() == pk.lower()]
    if len(hits) == 1 and not (child is parent and hits[0] == pk):
        return [hits[0]], [pk]
    return None


def build_edge(r: dict, entities: dict[str, dict]) -> dict:
    a, b = r["a"], r["b"]
    ca, cb = r["ca"], r["cb"]
    assumptions: list[str] = []
    ea, eb = entities[a], entities[b]

    # Direction: the "many" side holds the FK; otherwise use FK-name evidence.
    if ca[1] == "many" and cb[1] == "one":
        swap = False
    elif ca[1] == "one" and cb[1] == "many":
        swap = True
    else:
        fa, fb = _fk_match(ea, eb), _fk_match(eb, ea)
        if fb and not fa:
            swap = True
        else:
            swap = False
            if not fa:
                assumptions.append(f"FK side not determinable; left entity {a!r} taken as source")
    if swap:
        src, tgt, cs, ct = b, a, cb, ca
    else:
        src, tgt, cs, ct = a, b, ca, cb

    scols: list[str] = []
    tcols: list[str] = []
    if not (cs[1] == "many" and ct[1] == "many"):
        match = _fk_match(entities[src], entities[tgt])
        if match:
            scols, tcols = match
            assumptions.append(f"FK column inferred by name: {src}.{scols[0]} -> {tgt}.{tcols[0]}")

    return {
        "source": src,
        "target": tgt,
        "source_columns": scols,
        "target_columns": tcols,
        "cardinality": {
            "source": {"min": cs[0], "max": cs[1]},
            "target": {"min": ct[0], "max": ct[1]},
        },
        "identifying": r["identifying"],
        "label": r["label"],
        "assumptions": assumptions,
    }


def to_draft(parsed: dict, graph_name: str | None, source_file: str | None) -> dict:
    return {
        "format_version": 1,
        "graph_name": graph_name if graph_name is not None else parsed["title"],
        "source": {
            "format": "mermaid",
            "files": [source_file] if source_file else [],
            "description": parsed["title"],
        },
        "vertices": [
            {"id": e["table"], "table": e["table"], "schema": None,
             "description": e["description"], "columns": e["columns"]}
            for e in parsed["entities"].values()
        ],
        "edges": parsed["edges"],
        "notes": parsed["notes"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="Mermaid file (.mmd/.md) or - for stdin")
    p.add_argument("--graph-name", help="graph (database) name; defaults to the diagram title, if any")
    p.add_argument("--source-file", help="path recorded in source.files (default: INPUT)")
    args = p.parse_args(argv)
    try:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        parsed = parse(text)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    source_file = args.source_file or (None if args.input == "-" else args.input)
    print(json.dumps(to_draft(parsed, args.graph_name, source_file), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
