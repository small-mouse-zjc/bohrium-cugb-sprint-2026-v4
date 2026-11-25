---
name: paper-evidence-notes
description: 'Produce searchable paper cards, section-aligned notes and evidence-linked results, including limitations and unresolved or conflicting evidence.'
---

# 文献总结与结构化笔记

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Workflow

1. Build the section outline from headings and document order, not headings in the abstract or references. Identify citations to earlier work and keep those assertions separate from the focal paper's findings. Assign paper IDs before cross-paper synthesis. Catalog tables, figures and supplements with file and location.
2. Create a paper card with metadata, research question, design, data, population or setting, comparison, outcomes, main findings, limitations and replication prerequisites. A card field should carry an evidence ID, an explicit reported state and its scope. Supplement the card with section notes for requested sections. Aim for one independently checkable claim per note.
3. For numeric results identify metric, units, group, time, denominator and comparator. Include uncertainty measures as labeled in the paper. Distinguish direct estimates from secondary calculations and provide derivation when useful. When text and a table disagree, record both and describe which applies to the requested scope. Record whether a caveat was author-stated or inferred from the evidence.
4. Keep an evidence ledger with `id`, `file`, `locator` and `quote` (or `observed_value` for tables/figures). Use page plus heading and paragraph marker, or table/row/column, to anchor. Record caveats using “reported”, “not reported”, “inaccessible” or “conflicting”. Validate anchors by reopening them for the main findings, quantitative values and limitations. Use `python3 audit.py ledger evidence.json audit-report.json` to catch duplicate or incomplete records.
5. Export requested editable notes and structured fields. For a cross-paper question, include a matrix that retains each paper's own comparator and finding, then give a bounded synthesis. Show the evidence ID on each fact row for later retrieval.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic evidence item `{"id":"e02","file":"sample.pdf","locator":"PDF p. 4, Table 1, row S2, Model B","observed_value":"n = 24"}`. Machine validation checks structure. Open the cited cell to validate content.
