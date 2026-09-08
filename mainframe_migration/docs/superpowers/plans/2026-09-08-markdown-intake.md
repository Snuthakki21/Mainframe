# Markdown Process Intake Implementation Plan

> Agent execution: independent parser, flow integration, and operator documentation tasks, followed by combined review and verification.

**Goal:** Accept one Markdown document per process throughout the existing migration workbench and publish the complete framework on one testable branch.

**Architecture:** Dispatch intake by file extension into the existing inventory row contract. Retain documentation and source provenance in a normalized process flow, while JCL/COBOL remain the execution authority. Continue to use the existing target generation, registration, comparison, and report pipeline.

**Tech stack:** Python 3.10+ standard library, existing native Python/Java/C# generation and SQLite/Oracle/BigQuery targets.

**Design basis:** The operator's supplied job headings and section tables, including input/output tables, output-only acquisition tables, description-only tables, and NONE markers.

## Constraints

- No Excel conversion service or new runtime package dependency.
- Existing workbook configurations remain readable.
- Preserve source behavior, sealed artifacts, and baseline bytes.
- Do not infer executable rules, scheduler order, layouts, or physical destinations from prose.
- Keep target selection in target.json and label missing runtime/live database evidence accurately.
- Base the delivery on the complete upstream main tree at acd53ef4e15daebdc99ff41f9f57f9573addd50a; no other upstream branches or pull requests were present.

## Tasks

- [x] Add Markdown parsing and malformed-input tests in migration/inventory.py, migration/markdown_inventory.py, and tests/test_markdown_inventory.py. Keep job, step, program, inputs, outputs, row; add source, section, description, fields_present, and documentation_only metadata.
- [x] Integrate normalized process flow and explicit dataset destinations into discovery, both runners, reports, and target agent requests. Verify source conflicts, documentation-only rows, missing bindings, and request freshness.
- [x] Update modernize.py initialization to accept Markdown, persist optional output and target paths, and reject invalid process names before writing configuration. Test through the actual CLI entrypoint.
- [x] Switch the executable sample to equivalent Markdown, add a labeled screenshot-format example, and update operator/agent instructions and the migration skill.
- [x] Run parser/CLI tests, the complete existing suites, the Markdown sample, and all nine target selections. Retain measured evidence and refresh the shipped package manifest after final changes.
- [ ] Review the final diff and publish a branch whose parent is the inspected upstream commit. Verify the remote tree against the tested local content.
