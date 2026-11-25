---
name: reference-integrity-audit
description: 'Audit and reconcile scholarly in-text citations, bibliography records and DOI metadata with conservative deduplication and numbering.'
---

# 参考文献与引用管理

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

For numeric citations, first build an old-key to record map, resolve exact-DOI candidates against author and year, and deduplicate only with corroboration. Then build a single old-key to new-number plan in first-occurrence order before applying any edits. Use that same plan on the text and the reference list so a newly written number cannot be treated as an old one in a second replacement. Keep particles with surnames such as van der Berg. Leave unsupplied metadata empty. Return the old-to-new map and a record-level provenance table with the updated document, and run references on the final occurrences and final list.


1. Identify source format, supplied bibliographic data and the required style. Record every in-text occurrence with its actual anchor, syntax and current key. For numeric styles expand ranges only in explicit citation contexts and preserve group order, prefixes and locators. Skip math intervals, bracketed variable indices, equations, verbatim blocks and false-positive bracket sequences. Include captions and footnotes if in scope.
2. Normalize DOI case, URL prefix and whitespace for comparison. Resolve exact DOI duplicates only after checking type and title compatibility. Without DOI require stronger combined match of normalized title, lead author and year, checking editions, corrections, conference/journal versions, preprints and translations. A missing DOI is not reason to invent one. Keep unresolved records and a proposed merge map.
3. Match occurrences and bibliography in both directions, noting ambiguous and orphan references. Audit whether citations support the exact local claim when article material is available. Keep source forms for chapter, dataset, software or websites, with version/retrieval fields when required. Use official publisher/DOI metadata only when available and record the verification route.
4. Apply style and permitted changes in an editable file. Number from first occurrence when the selected style requires it, including parenthetical/caption occurrences as specified. Update citations and list via the same original-to-new map before recompressing ranges. Preserve identifiers even when rendering short titles or abbreviated journal names. For TeX use the project's existing BibTeX/Biber workflow and verify from the actual compile. Test bibliography closure with `python3 audit.py references refs.json audit-report.json`.
5. Deliver updated manuscript/bibliography and a reconciliation report of matched, missing, duplicate, unused and unresolved references. Review sampled citations where a reorder or merge changed the old number. Do not label network-inaccessible verification as completed.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic audit input `{"citations":[{"key":"r1","locator":"Methods paragraph 3"}],"references":[{"key":"r1","title":"Sample paper"}]}`. Run `python3 audit.py references refs.json audit-report.json`.
