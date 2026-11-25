---
name: academic-edit-provenance
description: 'Polish supplied academic prose with minimal meaning-preserving edits, consistent terminology and a sentence-linked revision record.'
---

# 学术语言润色

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Write the complete revised text before the audit. If the case supplies a draft revision for auditing, keep it and produce the requested review. Record each sentence-group mapping including splits and merges, with before/after spans and reason. Run audit.py invariants after drafting. Review flagged changes using exact local clauses. If a negation, hedge or comparator moved, resolve its scope manually before deciding whether to revert. The audit is a triage signal and cannot prove preservation of sentence meaning.


1. Read requested scope, language, author preference and target journal guidance, if supplied. Identify citation keys and numbering, equations, variables, names, terms, units, quantitative results and markers for uncertainty, negation and comparison. Preserve unrequested sections and preserve markup. IDs should refer to the original section, paragraph and sentence even if polished prose splits or merges sentences.
2. Draft grammar, discourse and terminology corrections with minimal intervention. Preserve evidential modality, causal versus correlational language, population and mechanism scope, comparative direction and numeric denominators. Match a target venue convention only if known. Keep the user's preferred terminology unless it is clearly inconsistent with their own definitions. Collect any competing term renders in the change record.
3. For editable DOCX retain source structure and styles where practical. For LaTeX preserve separate source commands, comments and bibliography keys. For bilingual tasks align the output by original sentence group. Record significant changes using original text, revised text, reason and review risk. If a sentence cannot be clarified safely from context, flag it with the information needed.
4. Run `python3 audit.py invariants pairs.json audit-report.json` to surface changes to numbers, citation groups and inline math. Review any warnings against the source and manually check negation, qualification and logical linkage. Verify coverage of all requested sections and consistency of definitions and acronyms.
5. Deliver a complete polished copy in the requested format and a separate audit/change record. When editing a binary document, use available rendering utilities to produce and inspect a real preview. Report in the result which exact sections and formats were processed.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic pair `{"id":"methods.3.2","source":"Table 2 presents the accuracies of 5 trials.","target":"Table 2 reports accuracy across 5 trials."}`. Audit paired records as a JSON array. Keep verb changes separate from any claim that the source could not support.
