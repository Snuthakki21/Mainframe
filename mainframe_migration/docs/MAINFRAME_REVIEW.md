# Skeptical review — completed checks and open findings

This is an adversarial review performed in the assistant session. It is not an
independent third-party audit, certification, or approval for bank production.

## Addressed by executable checks

- Competing target settings: central-file validation and conflicting-process tests.
- False target reuse: pair-specific artifact identity and switch/switch-back tests.
- Loss of source schema: logical source types/precision/keys preserved before DDL.
- Hidden SQLite assumptions: database-free native job emitters and selected adapters.
- Schema capability loss: BigQuery key enforcement retained as a blocker.
- Corrupted delivery/history: file-set seals, cache seals and registry checksums.
- Changed expected data: frozen baseline hashes checked before conversion/execution.
- Changed source: only affected models/code regenerated in a regression test.
- Agent stale target/source, invented references or overwrite: registration rejected.
- Uncommitted writes: not patched with an inferred COMMIT.
- Binary floating-point money: exact conversions reject float/overflow.
- SQL binding: values remain separate from Oracle SQL text.
- BigQuery session reuse: explicit BEGIN, session ID, bound DML and COMMIT tested
  using a fake transport; this is not live BigQuery execution.
- Uncertain remote outcome: no automatic retry or false rollback-success claim.
- Candidate isolation: build and execution use copies, not immutable generation files.

## Defects found while extending the framework

The agent registration initially used the wrong paths dictionary key; the handoff
suite exposed the error and the framework key was corrected. Python's BigQuery
adapter initially validated project+dataset together and admitted a hyphen in a
dataset; a failing transport-guard test led to separate validation. The .NET build
plan was corrected to separate restore --configfile from build --no-restore.
These are framework corrections. Synthetic source rules and expected outputs
were not repaired. Development logs are in evidence/v2.

## Remaining material gaps

.NET native compilation/execution and provider loading are untested here. Java
JDBC providers and Oracle/BigQuery live APIs are untested. Remote DDL and transactional
semantics require actual target integration evidence. General mainframe constructs
listed in SUPPORT_AND_LIMITS are not supported by this bounded front end. The live
Copilot/Devin generation route has contract tests, not an exercised vendor session.
No independent reviewer, full Windows runtime, throughput/scale, transitive bank
feed lock, production UI or deployment/data-migration test is claimed.

The exact-ZIP report separates these gaps from passes. A clean regression result
must not be described as complete target equivalence or universal modernization.
