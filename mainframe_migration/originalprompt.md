Set up and execute this migration for me. Run the necessary terminal
commands yourself; do not give me a checklist of commands to run.

My workspace is:
C:\Users\<my username>\OneDrive - Wells Fargo\Downloads\pts

Resolve my actual Windows username automatically.

Folders relative to this workspace:
- Framework: mainframe_migration
- Mainframe source: App-sn-PTS-modernization
- Process: SN002DA
- Output root: migration-results

Read mainframe_migration/AGENTS.md,
mainframe_migration/.agents/skills/migrate-process/SKILL.md,
and the relevant framework documentation.

1. Verify the environment

Run from mainframe_migration. Detect Python, including the py -3
launcher if necessary. Run doctor, the Windows package verifier,
and the synthetic demo.

Perform package verification before modifying shipped files.
Inspect the actual verification receipt and logs. Do not conceal
file-hash mismatches or treat skipped checks as passed.

Use Python and SQLite for this migration, with target.json as
the single authority for those settings.

2. Prepare my process

Locate the complete Markdown file I supplied and record its actual
local path. Create supporting folders as needed. Do not substitute
the incomplete screenshot example for my full process document.

Create or reuse processes/SN002DA/process.json. Verify its paths,
agent generation mode, source format, and output destination.

Inspect the source repository to establish all documented jobs,
steps, programs, copybooks, control members, database objects,
dataset bindings, destinations, and execution order.

Resolve everything supported by the source before asking me questions.
Do not invent business logic, mappings, or expected results.

3. Complete the migration

Drive discovery, source analysis, Python/SQLite generation, review,
registration, execution, and comparison yourself.

Follow the framework's candidate and registration contracts.
After relevant configuration changes, obtain a fresh agent request.

You are authorized to fix framework or integration defects and
create new versioned candidate attempts when needed. Preserve
previous sealed attempts and their evidence.

Preserve mainframe business behavior. Never change authoritative
expected outputs or weaken comparisons to make a test pass.

4. Test and report

Run the shipped tests, including workstation simulations.
For available real-process cases, check output file contents,
SQLite database contents, return codes, and repeatability.

Keep synthetic results separate from real-process validation.
Investigate failures and continue through recoverable issues.
Ask me only for genuinely missing information or required access.

Finish with:
migration-results/SN002DA/modernization_report.html

Open the report and summarize what ran, what passed, where the
generated code and outputs are, and any remaining blockers.
