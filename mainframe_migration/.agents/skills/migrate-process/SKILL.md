---
name: migrate-process
description: Discover and migrate a source-linked mainframe process to the independently selected language and database in target.json, preserving behavior and reusing prior analysis.
---

# One agent-operated migration or retargeting

The operator supplies a repository path, Excel inventory, process name, and
available baseline evidence. Run the internal steps yourself. Do not ask the
operator to drive separate discover/convert/run/compare commands.

## Read and discover

Read AGENTS.md and target.json first. Use Python, Java, or C#/.NET as selected;
SQLite, Oracle, or BigQuery is a separate selection. Create the process config
with `python modernize.py init` only when missing, then populate source-backed
file layouts, bindings and ordering using the repository evidence. Run:

`python modernize.py run --config processes/PROCESS/process.json`

Read the resulting consolidated report and agent_request.json. Investigate all
safe dependency paths before collecting one current list of plain-English gaps.
A new supplied dependency can reveal more questions; do not promise omniscience.

## Generate or retarget

Read docs/AGENT_CONTRACT.md. Source code, copybooks, original DDL and approved
knowledge define behavior. Prior SQLite output is not the logical data model.
Check request.reuse_candidates and target_registry.json before spending credits.
Preserve eligible same-language job files; regenerate only target-specific parts
when changing databases. When changing language, use the source-linked behavior
model when available, not a chain of lossy source-to-source translations.

Generate a complete native candidate directory matching the requested target and
entry-point contract. It has one native file per job, selected database adapter,
shared runtime, full target DDL, logical schema, dependency declarations and a
package.json. Use the templates in migration/targets/templates and the generated
sample as concrete references, not a license to silently ignore unsupported code.
Do not use the deterministic synthetic compiler as a substitute for a live agent
migration of a real process. Unsupported source/DDL/lifecycle requirements remain
visible blockers unless fully implemented and evidenced in the candidate contract.

## Read-only review and registration

Review for lost branches, changed arithmetic, changed sort/matching behavior,
lost SQL conditions, missing objects, changed transaction boundaries, and changes
to test evidence. Record source/target locations, reviewer and method honestly.
Do not repair the candidate to force a pass. Do not make business-rule changes.

Register it with:

`python modernize.py register-target --request RUN/agent_request.json --candidate CANDIDATE --review REVIEW.json`

Then run the same process command again. This is all one agent kickoff; these
internal commands are not manual steps for the operator. Requests/candidates are
sealed against source and target fingerprints. A stale or modified delivery is
blocked, not silently regenerated or repaired. New separately authorized attempts
use an explicitly increased agent_generation_version in the process config.

## Validate and report

The verifier compiles available native runtimes, runs cases in fresh work folders,
compares exact bytes, complete database snapshots or explicitly labeled database
operation traces, and checks each return code. It does not run remote DBs by default.

Never equate contract recording with a live Oracle/BigQuery test. Missing .NET or
JDBC drivers remain NOT_RUN. Keep the one report at output/PROCESS/
modernization_report.html current. Questions must be in mainframe/business English.
Reuse saved approved answers scoped to their process/global applicability, with
source evidence. Never globally memorize a process-specific interpretation.
