---
name: paper-evidence-graph
description: 'Build a literature knowledge graph with conservative entity resolution, source-backed directed edges and machine-readable exports.'
---

# 文献知识图谱构建

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Workflow

1. Define typed entities and canonical directed relation vocabulary from the assignment. For relations such as measures, uses and compares-with, define endpoint types, direction and when an edge is reciprocal. Represent observations with different population, condition, metric or time as scoped edges or observation nodes. Avoid upgrading an association to causation or an author claim to general truth.
2. Make a document and mention register with `source_id`, observed name, aliases and original position. Merge terms only with a reliable identifier, an explicit alias in context or agreement on type and defining context. Treat case, Unicode variation and punctuation as match candidates. Keep homonyms, incompatible species/materials, versions, populations and separately defined metrics separate.
3. For each edge keep subject, predicate, object, evidence ID(s), polarity, scope and curator notes. Choose evidence close to the original finding. Preserve contradictory edges as separate scoped statements and keep an index of conflicts. Merge repeated edges only when endpoints, scope, relation direction and polarity match. Union their evidence lists.
4. Export nodes and edges as JSON and the requested interchange format. For CSV keep IDs as strings and quote fields through a real serializer. For graph illustration carry over node and edge IDs so that labels are inspectable. Run `python3 audit.py graph graph.json graph-audit.json` to catch duplicate entity IDs, dangling endpoints and absent evidence. Then exercise case-requested queries and report actual answers with paths and citations.
5. Include assumptions, unresolved aliases, source coverage and a short example query. An updated graph must preserve prior IDs where entities are unchanged. Keep a merge/rename map so prior citations stay resolvable.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic graph usage: `python3 audit.py graph graph.json graph-audit.json`. A link may be `{"source":"method-1","relation":"measures","target":"variable-1","evidence":["e1"]}` where both endpoints and `e1` are declared.
