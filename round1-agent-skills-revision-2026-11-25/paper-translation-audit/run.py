"""Case preparation and artifact finalization for the CUGB research Skills."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


PROFILE = "paper-translation-audit"
TEXT_SUFFIXES = {".txt", ".md", ".tex", ".csv", ".tsv", ".json", ".jsonl", ".bib", ".log", ".yaml", ".yml"}
FIELD_ALIASES = ("source_text", "original", "draft", "text", "content")
MISSING = object()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".skill-", suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def find_text(value, depth=0):
    if depth > 2 or not isinstance(value, dict):
        return None
    for key in FIELD_ALIASES:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    for key in ("input", "inputs", "material", "document", "payload"):
        found = find_text(value.get(key), depth + 1)
        if found:
            return found
    return None


def inventory(base):
    files, texts = [], {}
    for file in sorted(base.rglob("*")):
        if file.is_symlink() or not file.is_file():
            continue
        name = file.relative_to(base).as_posix()
        if name in ("case.json", "task.md"):
            continue
        entry = {"file": name, "bytes": file.stat().st_size}
        if file.suffix.lower() in TEXT_SUFFIXES and 0 < entry["bytes"] <= 2_000_000:
            try:
                with file.open(encoding="utf-8-sig", newline="") as stream:
                    texts[name] = stream.read()
            except (OSError, UnicodeError):
                entry["text_status"] = "unreadable"
        files.append(entry)
    return files, texts


def anchor_catalog(name, text):
    """Half-open Python string offsets in the unmodified decoded source."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    entries = []
    page_start = 0
    for page, segment in enumerate(text.split("\f"), 1):
        boundaries = [0]
        for match in re.finditer(r"\r?\n[ \t]*\r?\n|(?m:^[ \t]*(?:#{1,6}\s|(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.)[ \t]+[A-Z]))", segment):
            boundaries.extend([match.start(), match.end()] if "\n" in match.group(0) else [match.start()])
        boundaries.append(len(segment))
        for block, (left, right) in enumerate(zip(boundaries, boundaries[1:]), 1):
            part = segment[left:right]
            if not part.strip():
                continue
            start = page_start + left + len(part) - len(part.lstrip())
            end = page_start + left + len(part.rstrip())
            entries.append({"id": f"p{page}-b{block}", "file": name, "page": page if "\f" in text else None,
                            "start": start, "end": end, "source_sha256": digest, "quote": text[start:end]})
        page_start += len(segment) + 1
    return entries


def verify_anchors(rows, sources):
    checks = []
    digests = {name: hashlib.sha256(source.encode("utf-8")).hexdigest() for name, source in sources.items()}
    for row in rows:
        if not isinstance(row, dict):
            checks.append({"id": None, "verified": False})
            continue
        source = sources.get(row.get("file"))
        start, end = row.get("start"), row.get("end")
        quote = row.get("quote")
        expected_digest = row.get("source_sha256")
        verified = (isinstance(source, str) and type(start) is int and type(end) is int
                    and isinstance(quote, str) and bool(quote.strip()) and 0 <= start < end <= len(source)
                    and source[start:end] == quote
                    and (expected_digest is None or expected_digest == digests.get(row.get("file"))))
        checks.append({"id": row.get("id"), "file": row.get("file"), "verified": verified})
    count = sum(row["verified"] for row in checks)
    return {"verified": count, "total": len(checks), "rate": count / len(checks) if checks else None, "checks": checks}


def contract_fields(contract):
    if isinstance(contract, list):
        fields = {}
        for item in contract:
            if isinstance(item, str):
                fields[item] = {}
            elif isinstance(item, dict):
                name = item.get("name") or item.get("key") or item.get("field")
                if isinstance(name, str):
                    fields[name] = item
        return fields
    if not isinstance(contract, dict):
        return {}
    properties = contract.get("properties")
    if isinstance(properties, dict):
        return properties
    if isinstance(contract.get("fields"), (dict, list)):
        return contract_fields(contract["fields"])
    if isinstance(contract.get("required"), list):
        return contract_fields(contract["required"])
    return {key: spec for key, spec in contract.items() if key not in
            {"type", "description", "title", "examples", "$schema", "additionalProperties", "artifacts", "artifact_names"}}


def fallback(spec):
    if not isinstance(spec, dict):
        return None
    if "const" in spec:
        return spec["const"]
    if "default" in spec:
        return spec["default"]
    kind = spec.get("type")
    if isinstance(kind, list) and "null" in kind:
        return None
    if kind == "array":
        return []
    if kind == "object":
        return {key: fallback(value) for key, value in contract_fields(spec).items()}
    if kind == "string":
        return "not_reported" if not spec.get("enum") else next(
            (item for item in spec["enum"] if item in ("not_reported", "unknown", "partial", "cannot_determine")), None)
    return None


def complete(value, spec):
    if value is MISSING:
        return fallback(spec)
    if isinstance(value, dict) and isinstance(spec, dict):
        fields = contract_fields(spec) if spec.get("type") == "object" or "properties" in spec else {}
        return {**value, **{key: complete(value.get(key, MISSING), field) for key, field in fields.items()}}
    return value


def status_of(draft, fields, missing, issues, artifacts, preparation_only):
    requested = draft.get("status")
    metadata = {"case_id", "status", "sources", "warnings", "uncertainty", "limitations", "changes", "provenance"}
    has_content = any(key not in metadata and value not in (None, "", [], {}) for key, value in draft.items()) or bool(artifacts)
    if preparation_only or not has_content:
        candidate = "cannot_determine"
    elif missing or issues or requested in ("partial", "cannot_determine", "failed", "rejected"):
        candidate = "partial"
    else:
        candidate = "success"
    spec = fields.get("status")
    allowed = spec.get("enum") if isinstance(spec, dict) else None
    if isinstance(allowed, list) and candidate not in allowed:
        return next((v for v in (requested, "partial", "cannot_determine", "unknown", "failed")
                     if v in allowed and v != "success"), candidate)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("/input"))
    parser.add_argument("--output", type=Path, default=Path("/app/output"))
    parser.add_argument("--work", type=Path, default=Path("/app/work"))
    parser.add_argument("--draft", type=Path, help="Candidate result JSON containing case-specific answers")
    args = parser.parse_args()
    root = args.input.parent if args.input.is_file() else args.input
    case_path = args.input if args.input.is_file() else root / "case.json"
    draft, fields, case_id = {}, {}, None
    strict = False
    issues = []
    try:
        try:
            case = read_json(case_path)
            if not isinstance(case, dict):
                raise ValueError("case JSON must be an object")
        except (OSError, ValueError, UnicodeError) as error:
            case = {}
            issues.append(f"Case metadata unavailable ({type(error).__name__}).")
        case_id = case.get("case_id", case.get("id"))
        contract = case.get("output_contract")
        fields = contract_fields(contract)
        strict = isinstance(contract, dict) and contract.get("additionalProperties") is False and bool(fields)
        if not fields:
            issues.append("No explicit output field schema found. Follow task.md for deliverables.")
        if args.draft:
            candidate = read_json(args.draft)
            if not isinstance(candidate, dict):
                raise ValueError("candidate result must be an object")
            draft = candidate
        files, sources = inventory(root)
        inline = find_text(case)
        if inline:
            sources["case.json#embedded-text"] = inline
        # PDF text requires a native extraction or visual anchors. Keep that representation
        # distinct from literal offsets into a text source supplied by the case.
        if PROFILE in ("paper-evidence-notes", "academic-edit-provenance", "paper-translation-audit", "introduction-evidence-map"):
            catalog = {name: anchor_catalog(name, text) for name, text in sources.items()
                       if name.endswith((".txt", ".md", ".tex")) or name == "case.json#embedded-text"}
            write_json(args.work / "source-anchors.json", catalog)
        write_json(args.work / "case-inventory.json", {"case_id": case_id, "files": files, "issues": issues,
                                                        "contract_fields": list(fields)})
        source_anchors = draft.get("source_anchors")
        if isinstance(source_anchors, list):
            verified = verify_anchors(source_anchors, sources)
            write_json(args.work / "anchor-verification.json", verified)
            failures = [row for row in verified["checks"] if not row["verified"]]
            if failures:
                issues.append(f"{len(failures)} supplied text anchors failed source comparison.")
            if "anchor_verification" in fields:
                draft["anchor_verification"] = verified
    except (OSError, ValueError, TypeError, AttributeError, UnicodeError) as error:
        issues.append(f"Preparation or finalization stopped at {type(error).__name__}.")
    missing = [key for key in fields if key not in ("case_id", "status") and draft.get(key) is None]
    artifacts = []
    try:
        artifacts = [file.relative_to(args.output).as_posix() for file in args.output.rglob("*")
                     if file.is_file() and not file.is_symlink() and file.name != "result.json" and not file.name.startswith(".")]
    except OSError:
        issues.append("Artifact inventory unavailable.")
    result = {**({} if strict else draft), **{key: complete(draft.get(key, MISSING), spec) for key, spec in fields.items()}}
    if case_id is not None or "case_id" not in draft:
        result["case_id"] = case_id
    if not strict or "status" in fields:
        result["status"] = status_of(draft, fields, missing, issues, artifacts, args.draft is None)
    if issues or missing:
        write_json(args.work / "finalization-review.json", {"issues": issues, "unfilled_fields": missing, "artifacts": artifacts})
        limitations = issues + [f"Unfilled case field: {key}" for key in missing]
        if "limitations" not in result and not strict:
            result["limitations"] = limitations
        elif isinstance(result.get("limitations"), list):
            result["limitations"] = list(dict.fromkeys(result["limitations"] + limitations)) if all(
                isinstance(value, str) for value in result["limitations"]) else result["limitations"]
    result_path = args.output / "result.json"
    if args.draft is not None or not result_path.exists():
        write_json(result_path, result)


if __name__ == "__main__":
    main()
