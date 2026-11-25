---
name: paper-evidence-graph
description: 'Build a literature knowledge graph with conservative entity resolution, source-backed directed edges and machine-readable exports.'
---

# 文献知识图谱构建

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Use one canonical entity register for both edge creation and queries. For every alias store the exact mention, normalization used, requested type, source locator and evidence for the resolution. Resolve query endpoints through that same register. Give a candidate set and provenance on ambiguity. Log a merge only when a stable ID or explicit contextual equation supports it. Include query paths as edge IDs and cite each supporting source.


1. Define typed entities and canonical directed relation vocabulary from the assignment. For relations such as measures, uses and compares-with, define endpoint types, direction and when an edge is reciprocal. Represent observations with different population, condition, metric or time as scoped edges or observation nodes. Avoid upgrading an association to causation or an author claim to general truth.
2. Make a document and mention register with `source_id`, observed name, aliases and original position. Merge terms only with a reliable identifier, an explicit alias in context or agreement on type and defining context. Treat case, Unicode variation and punctuation as match candidates. Keep homonyms, incompatible species/materials, versions, populations and separately defined metrics separate.
3. For each edge keep subject, predicate, object, evidence ID(s), polarity, scope and curator notes. Choose evidence close to the original finding. Preserve contradictory edges as separate scoped statements and keep an index of conflicts. Merge repeated edges only when endpoints, scope, relation direction and polarity match. Union their evidence lists.
4. Export nodes and edges as JSON and the requested interchange format. For CSV keep IDs as strings and quote fields through a real serializer. For graph illustration carry over node and edge IDs so that labels are inspectable. Run `python3 audit.py graph graph.json graph-audit.json` to catch duplicate entity IDs, dangling endpoints and absent evidence. Then exercise case-requested queries and report actual answers with paths and citations.
5. Include assumptions, unresolved aliases, source coverage and a short example query. An updated graph must preserve prior IDs where entities are unchanged. Keep a merge/rename map so prior citations stay resolvable.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic graph usage: `python3 audit.py graph graph.json graph-audit.json`. A link may be `{"source":"method-1","relation":"measures","target":"variable-1","evidence":["e1"]}` where both endpoints and `e1` are declared.
