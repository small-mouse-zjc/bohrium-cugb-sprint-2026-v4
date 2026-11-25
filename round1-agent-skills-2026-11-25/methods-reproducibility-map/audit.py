"""Deterministic checks for source-aligned scholarly artifacts (Python 3.9+)."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import quote


NUMBER = re.compile(
    r"(?<![\w.])[−+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:[eE][−+-]?\d+)?(?:\s*[%‰])?"
)
CITATION = re.compile(
    r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]|\\(?:cite\w*|ref|eqref|autoref)"
    r"(?:\[[^\]\n]*\])*\{[^}\n]+\}"
)
MATH = re.compile(r"(?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)\$[^\n$]+?(?<!\\)\$|\\\(.+?\\\)|\\\[.+?\\\]", re.S)


def issue(items, key, detail):
    items.append({"item": key, "issue": detail})


def index_rows(rows, id_field, issues):
    found = {}
    for row in rows:
        key = row.get(id_field)
        if not isinstance(key, str) or not key.strip():
            issue(issues, None, f"missing {id_field}")
        elif key in found:
            issue(issues, key, f"duplicate {id_field}")
        else:
            found[key] = row
    return found


def inspect_invariants(rows, issues):
    for key, row in index_rows(rows, "id", issues).items():
        source, target = row.get("source"), row.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or not target.strip():
            issue(issues, key, "missing source or target text")
            continue
        for label, pattern in (("number", NUMBER), ("citation", CITATION), ("inline math", MATH)):
            old = Counter(pattern.findall(source.replace("−", "-")))
            new = Counter(pattern.findall(target.replace("−", "-")))
            if old != new:
                issues.append({"item": key, "issue": f"{label} changed",
                               "removed": list((old - new).elements()),
                               "added": list((new - old).elements())})


def inspect_ledger(rows, issues):
    index = index_rows(rows, "id", issues)
    for key, row in index.items():
        if not row.get("file") or not row.get("locator"):
            issue(issues, key, "missing file or locator")
        if not row.get("quote") and row.get("observed_value") is None:
            issue(issues, key, "missing quote or observed value")
    return index


def inspect_graph(data, issues):
    nodes = index_rows(data["nodes"], "id", issues)
    evidence = inspect_ledger(data["evidence"], issues)
    edge_ids = set()
    for position, edge in enumerate(data["edges"], 1):
        key = edge.get("id", f"edge {position}")
        if key in edge_ids:
            issue(issues, key, "duplicate edge ID")
        edge_ids.add(key)
        if edge.get("source") not in nodes or edge.get("target") not in nodes:
            issue(issues, key, "missing source or target node")
        if not edge.get("relation"):
            issue(issues, key, "missing directed relation")
        anchors = edge.get("evidence", [])
        if not isinstance(anchors, list) or not anchors or any(a not in evidence for a in anchors):
            issue(issues, key, "missing or unresolved evidence ID")


def inspect_references(data, issues):
    references = index_rows(data["references"], "key", issues)
    used = set()
    for row in data["citations"]:
        key = row.get("key")
        if not row.get("locator"):
            issue(issues, key, "citation occurrence missing its locator")
        if key not in references:
            issue(issues, key, "citation missing from bibliography")
        else:
            used.add(key)
    for key in sorted(references.keys() - used):
        issue(issues, key, "bibliography record has no tracked occurrence")
    by_doi = {}
    for key, row in references.items():
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "",
                     str(row.get("doi") or "").strip().lower())
        if doi:
            previous = by_doi.setdefault(doi, key)
            if previous != key:
                issue(issues, key, f"same DOI as {previous}, verify before merging")


def inspect_latex(log, issues):
    patterns = (
        ("undefined", r"(?:Citation|Reference).*undefined|undefined (?:references|citations)"),
        ("duplicate", r"multiply defined|duplicate destination"),
        ("overflow", r"Overfull \\[hv]box"),
        ("error", r"^!|^.+:\d+: (?:LaTeX|Package|Undefined control)"),
        ("rerun", r"Rerun to get|rerunfilecheck Warning"),
    )
    for number, line in enumerate(log.splitlines(), 1):
        for label, pattern in patterns:
            if re.search(pattern, line, flags=re.I):
                issues.append({"line": number, "issue": label, "message": line.strip()})
                break
    if not log.strip():
        issue(issues, None, "build log is empty")


def nanopublications(rows):
    problems = []
    claims = inspect_ledger(rows, problems)
    for key, row in claims.items():
        for field in ("subject", "relation", "object", "quote"):
            if row.get(field) is None or not str(row[field]).strip():
                issue(problems, key, f"missing {field}")
        if row.get("support") not in (None, "direct", "qualified"):
            issue(problems, key, "only direct or qualified assertions can be exported")
    if problems:
        raise ValueError(json.dumps(problems, ensure_ascii=False))
    literal = lambda value: json.dumps(str(value), ensure_ascii=False)
    parts = [
        "@prefix np: <http://www.nanopub.org/nschema#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix local: <urn:skill:evidence-nanopublication:field:> .",
    ]
    for key, row in claims.items():
        uri = "urn:skill:evidence-nanopublication:" + quote(key, safe="")
        parts.extend([
            f"<{uri}:head> {{ <{uri}> a np:Nanopublication ; np:hasAssertion <{uri}:assertion> ;",
            f"  np:hasProvenance <{uri}:provenance> ; np:hasPublicationInfo <{uri}:pubinfo> . }}",
            f"<{uri}:assertion> {{ <{uri}:statement> a rdf:Statement ;",
            f"  local:subject {literal(row['subject'])} ; local:relation {literal(row['relation'])} ;",
            f"  local:object {literal(row['object'])} ; local:scope {literal(row.get('scope', ''))} . }}",
            f"<{uri}:provenance> {{ <{uri}:assertion> prov:wasDerivedFrom <{uri}:source> ;",
            f"  local:locator {literal(row['locator'])} ; local:quote {literal(row['quote'])} ;",
            f"  local:support {literal(row.get('support') or 'unspecified')} .",
            f"  <{uri}:source> local:file {literal(row['file'])} . }}",
            f"<{uri}:pubinfo> {{ <{uri}> local:extractor \"evidence-nanopublications\" ;",
            "  local:formatVersion \"1\" . }",
        ])
    return "\n\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("invariants", "ledger", "graph", "references", "latex", "nanopub"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        source = args.input.read_text(encoding="utf-8-sig", errors="replace" if args.mode == "latex" else "strict")
        issues = []
        if args.mode == "latex":
            inspect_latex(source, issues)
        else:
            data = json.loads(source)
            if args.mode == "nanopub":
                args.output.write_text(nanopublications(data), encoding="utf-8")
                return
            checks = {"invariants": inspect_invariants, "ledger": inspect_ledger,
                      "graph": inspect_graph, "references": inspect_references}
            checks[args.mode](data, issues)
        args.output.write_text(json.dumps({"check": args.mode, "issues": issues}, ensure_ascii=False,
                                         indent=2) + "\n", encoding="utf-8")
    except (KeyError, TypeError, AttributeError, OSError, ValueError) as error:
        parser.exit(2, f"{args.mode}: {error}\n")


if __name__ == "__main__":
    main()
