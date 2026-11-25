---
name: evidence-nanopublications
description: 'Extract atomic scientific assertions and their minimal supporting evidence and export self-contained nanopublication graphs with provenance.'
---

# Nanopublication

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

Make a field crosswalk from the current case schema before export. Assign requested confidence values only with a supporting reason and source scope. Keep graph namespace and mandatory keys exactly as specified by the case. Inspect the parsed graph for one navigable assertion, provenance graph and publication-info graph per head. When the case requires formal RDF statement terms, use rdf:subject, rdf:predicate and rdf:object with a stable IRI where possible. Keep the human-readable source mention, quotation and unresolved candidates in the case output.


1. Identify the requested claims and original sources. Split coordinated claims when the parts can stand independently. Keep essential population, condition, measurement window, comparator, units and modality within the assertion. Distinguish measured results, author interpretations, hypotheses and earlier work. Preserve a negative result's polarity. A result without a reported threshold is not evidence of equivalence.
2. For each candidate, locate the shortest sufficient supporting quotation or table/figure observation plus its file, physical page, section/paragraph or table coordinates. A caption alone rarely establishes an effect, and a methods paragraph alone cannot support a result. Keep multiple anchors when a conclusion needs both the result and its comparison definition. Record support as direct, qualified or unresolved with a concrete reason. Unresolved items belong in the review list.
3. Normalize identifiers using a verified DOI or supplied source ID. Give each statement a stable local ID and preserve subject, relation direction, object or measured value, evidence ID and provenance. For experimental context, use a separate scope object. Never label a local ID as a published or registered nanopublication identifier.
4. Export the requested JSON and, when suitable, TriG with a nanopublication head and separate assertion, provenance and publication-info named graphs. The head links all three graph IRIs. The provenance graph links the assertion graph to the actual source and holds evidence and attribution separately from publication metadata. The publication-info graph describes this extraction and its local version. Run `python3 audit.py nanopub claims.json assertions.trig` for a portable TriG export of supported claims. If RDFLib is available parse the file as TriG and check all four graph links per assertion. Check duplicate IDs and evidence anchoring by reopening sampled sources.
5. Include relation vocabulary definitions and failed or unresolved candidates with reasons. Use the case format and namespace requirements where specified. Preserve licensing/attribution distinctions and any uncertainty in the accompanying structured result.

## Use and limits

Run the bundled `audit.py` from this skill's folder with Python 3.9+, or invoke it by its absolute path. Audit findings are deterministic checks and should be reviewed against source evidence.

## Minimal example

Synthetic JSON input `[{"id":"n1","subject":"Sample A","relation":"has drying temperature","object":"30 °C","scope":"stated method","file":"sample.pdf","locator":"PDF p. 2, Methods","quote":"Sample A was dried at 30 °C."}]`. Run `python3 audit.py nanopub claims.json assertions.trig`.
