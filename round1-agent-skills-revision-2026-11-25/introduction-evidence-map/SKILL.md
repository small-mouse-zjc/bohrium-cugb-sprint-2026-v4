---
name: introduction-evidence-map
description: 'Draft evidence-backed paper introductions and related work using claim-to-source mappings and defensible gaps and contributions.'
---

# 引言与相关工作写作

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Write a complete introduction and related-work section that can be read without the evidence tables. Budget paragraphs for the domain problem, competing approaches at comparable settings, gap and contribution. Build each related-work paragraph around a contrast with a stated dimension and practical consequence. Prioritize filling any substantive gap in the prose before calculating evidence coverage. Check that each contribution addresses a gap named in the introduction and is supported by the supplied study.


1. Inventory supplied work, primary results, bibliography and audience. Separate evidence from the current paper versus earlier literature. Build a comparison matrix of competing approaches, shared problem setting, designs, data, evaluation axes, strengths and documented limitations. Link each meaningful cell to a source location. Compare like-for-like or state which settings differ.
2. Draw a bounded gap from observed evidence. Prefer “in the studies examined here…” with a named scope over exclusivity or priority assertions. If the corpus proves a gap in a named dataset or condition, bound the claim to that corpus and condition. Distinguish an untested setting, a known trade-off and conflicting evidence. Put missing primary sources on a coverage list.
3. Map each proposed contribution to the exact part of the paper that verifies it, such as method, primary experiment or figure. Match claims of novel design, empirical improvement and release of artifacts to different evidence types. If inputs support only a planned contribution, identify it as planned and avoid forecasting results.
4. Draft a coherent opening within requested length: problem and stakes, material constraint, relationship to prior work, bounded gap, then contributions. Organize related work by comparison dimensions relevant to the gap. Keep references adjacent to claims and follow the existing citation style. Use names/years or existing keys drawn from the verified bibliography.
5. Deliver editable prose, reference mapping and an evidence ledger. Run `python3 audit.py ledger evidence.json audit-report.json` to validate ledger structure. Re-read gap and contribution sentences in reverse order against their sources, downgrade unsupported generalizations, and verify citation closure with the bibliography. If material is weak, deliver bounded text and explicit evidence gaps.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic mapping example: `C3 → e07 (sample.pdf, PDF p. 6, Section 4.2, Table 2, model row)` records the source for a cohort-specific comparison. Use the requested prose artifact and machine-readable mapping.
