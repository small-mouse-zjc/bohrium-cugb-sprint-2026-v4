---
name: latex-build-audit
description: 'Repair, adapt and compile editable research LaTeX projects while preserving mathematical content, references and template requirements.'
---

# LaTeX 写作与编译

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Save editable sources before compiling and keep a snapshot of the best verified build. Treat a missing SOURCE_DATE_EPOCH as an ordinary build. Use an epoch only if supplied, valid and needed for deterministic comparison. Keep the baseline log and the actual final log separate. If a class, font or executable is unavailable, preserve the best revised source and give the first actionable diagnostic and exact command. Record an actual PDF only when created by the selected build. A preexisting PDF may be retained as an explicitly labeled reference when the task requires it.


1. Read the original task and inspect the project root, declared engine, main file, required class/style, bibliography tool, images and fonts. Identify the actual root from the instructions, existing build notes or a top-level document class. Inspect all trusted entrypoints and tool settings before compiling. Work on a local copy under /app/work with shell escape disabled. Use installed components and case-supplied assets.
2. Compile a baseline when possible, isolating each independent root cause in the log. Prioritize file/line errors, missing package/class/fonts, mismatched environments and malformed commands. Fix the smallest coherent source unit. Preserve equations and label/citation targets unless the task requests changes. Maintain table cell values and units and fit wide/tall tables via appropriate line breaks, flexible columns or multipage layout.
3. Use the project's documented engine where available. For a typical pdfLaTeX project run `latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error -pdflatex="pdflatex -no-shell-escape %O %S" -outdir=build main.tex` from the project. For XeLaTeX or LuaLaTeX set the corresponding latexmk mode and engine override. If latexmk is absent, use the appropriate engine and bibliography tool and rerun until references converge (compare auxiliary files and warnings, with a bounded number of passes).
4. Inspect the real final log with `python3 audit.py latex build/main.log audit-report.json`; read undecidable split or multiline warnings directly. Check unresolved citations and references, duplicate labels, overfull boxes, and engine/package information. Render first, changed and anomaly pages from the actual PDF. Compare formula symbols, table rows/columns, captions and references against source and assignment constraints.
5. Deliver source tree with all requisite editable files, build instructions, compiled PDF when available, and a concise log/change record. If build fails, save useful edited files and the real first remaining diagnostic with engine/version and file/line; a stale PDF belongs outside the success result.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic call `python3 audit.py latex build/main.log audit-report.json` after the real build. A report row for `Citation 's1' undefined` directs review to the bibliography and source key.
