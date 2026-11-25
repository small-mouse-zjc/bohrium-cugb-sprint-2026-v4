---
name: paper-translation-audit
description: 'Translate research papers into source-aligned bilingual output while protecting terminology, quantitative values, citations and mathematical notation.'
---

# 文献翻译

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Deliver the complete translation by section before polishing glossary entries. In the second pass, resolve long modifier chains by identifying the clause subject, main verb, logical connectors and scope of each modifier, then reconstruct natural target-language order. Translate figure captions and table headings within the requested range. Shift passive voice only when the original names the actor or the target sentence preserves the agentless claim. Keep equations, variables, quantities and citation positions linked to the original. Read each revised paragraph independently for fluency, then re-read both versions for technical equivalence.


1. Read the exact requested scope and target language. Separate captions, footnotes, table cells and references from body prose. Establish ordered IDs by section and source position before translation. Join a paragraph broken across pages only when layout and syntax support the join, recording both source spans. When PDFs have ambiguous order, verify from page renderings.
2. Build a glossary from the supplied terminology and first occurrence of important domain terms. Record source term, selected translation, allowed variants, abbreviation and evidence of its meaning. A user-supplied glossary has priority. Keep homonyms and symbol definitions scoped to their domain or section. Note only unresolved ambiguities.
3. Translate paragraph by paragraph with neighboring context. Preserve equations, numeric values, units, confidence intervals, ranges, citations and cross-references. Mask fragile spans with unique temporary placeholders when needed and verify one-to-one restoration. Keep target headings, lists and paragraph IDs aligned. Maintain any emphasis, time relation, negation, uncertainty and stated causal scope.
4. Reconcile the ordered input and output ID lists, checking missing, repeated and displaced paragraphs. To support review, run `python3 audit.py invariants pairs.json audit-report.json` on pairs in the format shown below. Reassign warnings caused by locale formatting only after confirming the underlying quantities and references are unchanged. Manually inspect a second pass for qualifier drift and terminology collisions.
5. Deliver the requested bilingual file and glossary. Include a location for each untranslated item and why it could not be converted (e.g., embedded illegible equation). Keep source text and editable translations in distinct columns or labeled blocks. Add changes for any deliberate normalizations requested by the user.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic audit input `[{"id":"p2-par3","source":"The signal may rise by 4%. [2]","target":"信号可能上升 4%。[2]"}]`. Run `python3 audit.py invariants pairs.json audit-report.json`. Machine flags are review prompts.
