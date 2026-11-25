---
name: methods-reproducibility-map
description: 'Write reproducible methods and experimental sections from supplied data, source code, configurations and run records with traceable provenance.'
---

# 方法与实验章节写作

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Start with a usable Methods draft and reproducibility matrix from the supplied material. Missing manifests, versions, split fields, seeds and run counts affect individual rows only. Use the case's unknown value for that row and list what would establish it. If train/test descriptions conflict, report each anchored reading and preserve every unambiguous processing step. Return editable prose and the completed portions of the matrix even if the expected logs or configuration are unavailable.


1. Inventory protocol notes, manuscript, code/config and actual runs. Build separate columns for proposed, configured, executed and observed quantities. For actual run values prefer run-specific configs and logs. If code defaults and completed runs disagree, preserve both with scope. Never treat a common default, a comment, or a hypothetical setting as a fact about completed work.
2. Build a reproducibility matrix with setting, value, unit, source anchor (file, symbol/line, log timestamp, page/section, table cell), run/group, and status. Cover data source/license where requested, version, collection, exclusions, transformations, split, software/hardware, settings, seeds, baselines, metrics, statistical procedure and repeated execution. Keep acquisition/calibration details or data-handling requirements if relevant to the research type.
3. Write Methods in execution order and Experimental Design around the hypotheses, conditions, comparisons and measurement. Define metric formulas, symbols and aggregation when the sources support them. Clarify the analysis unit and denominator, and distinguish actual settings across experiments. Tie each result in scope to the corresponding configuration, group and measurement. Do not invent seeds, replicate counts, p-values, apparatus precision or ethics approval.
4. Provide the usable prose, parameter/reproducibility table and unresolved list. If the request includes diagram or Word output, provide a real rendered preview when the environment supports it. If runnable instructions are requested, verify paths and commands or record precisely where actual execution stops. Record derived conversions and any inferred details as such.
5. Use `python3 audit.py ledger evidence.json audit-report.json` to check the source ledger. Reconcile every number, unit, seed and conditional path mentioned in the text against the run or protocol. Expose discrepancies in the result rather than choosing values by convention.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic provenance row: learning rate `0.002`, run `R2`, source `run-R2.log:48`, type `executed`, configuration note `defaults.yaml:7 was 0.001`. The two values retain distinct provenance.
