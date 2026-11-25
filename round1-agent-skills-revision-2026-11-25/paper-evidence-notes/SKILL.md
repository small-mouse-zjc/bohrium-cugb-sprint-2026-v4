---
name: paper-evidence-notes
description: 'Produce searchable paper cards, section-aligned notes and evidence-linked results, including limitations and unresolved or conflicting evidence.'
---

# 文献总结与结构化笔记

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Build a six-field reading card for the question, data, method conditions, findings, limitations and assumptions. Give each supported field one or more note IDs. When the source is text, record each note as an exact half-open character slice. Take the file, offsets and digest from the prepared catalog, or compute a shorter exact slice within that block. Supply the used slices in the candidate's source_anchors array for validation. Keep the independent interpretation beside the quote. For PDFs use page and bounding box, or explicitly identify the extraction file used for text offsets. Preserve uncovered sections and separate author-stated limitations from your interpretation.


1. Build the section outline from headings and document order, not headings in the abstract or references. Identify citations to earlier work and keep those assertions separate from the focal paper's findings. Assign paper IDs before cross-paper synthesis. Catalog tables, figures and supplements with file and location.
2. Create a paper card with metadata, research question, design, data, population or setting, comparison, outcomes, main findings, limitations and replication prerequisites. A card field should carry an evidence ID, an explicit reported state and its scope. Supplement the card with section notes for requested sections. Aim for one independently checkable claim per note.
3. For numeric results identify metric, units, group, time, denominator and comparator. Include uncertainty measures as labeled in the paper. Distinguish direct estimates from secondary calculations and provide derivation when useful. When text and a table disagree, record both and describe which applies to the requested scope. Record whether a caveat was author-stated or inferred from the evidence.
4. Keep an evidence ledger with `id`, `file`, `locator` and `quote` (or `observed_value` for tables/figures). Use page plus heading and paragraph marker, or table/row/column, to anchor. Record caveats using “reported”, “not reported”, “inaccessible” or “conflicting”. Validate anchors by reopening them for the main findings, quantitative values and limitations. Use `python3 audit.py ledger evidence.json audit-report.json` to catch duplicate or incomplete records.
5. Export requested editable notes and structured fields. For a cross-paper question, include a matrix that retains each paper's own comparator and finding, then give a bounded synthesis. Show the evidence ID on each fact row for later retrieval.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic evidence item `{"id":"e02","file":"sample.pdf","locator":"PDF p. 4, Table 1, row S2, Model B","observed_value":"n = 24"}`. Machine validation checks structure. Open the cited cell to validate content.
