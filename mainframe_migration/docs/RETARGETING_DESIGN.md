# Retargeting design and invariants

The selected pair is not a cosmetic output label. Source interpretation, native
code, database components and validation each have a separate identity.

1. Discovery identifies source dependencies and original DDL from the local checkout.
2. A portable behavior model retains supported source statements, layouts, calls,
   step ordering and utility operations. Its key includes relevant source bytes,
   parser/model version, source format, collation and approved scoped knowledge.
3. A language cache key adds the selected native language and emitter version.
4. A complete target artifact contains native jobs/runtime, selected DB adapter,
   source-derived DDL, logical schema, dependencies and the target profile.
5. Every validation uses a fresh execution copy and records its own baseline,
   runtime, compile result, mode and comparisons. No target inherits a pass.

Changing only DB reuses eligible source and language code. Changing language
reuses eligible source models and emits native code. Changed source invalidates
its dependent models/jobs; changed shared codebooks invalidate their users.
Schema changes regenerate schema/backend artifacts and may conservatively
invalidate source models whose dependency list includes the schema. Runtime or
adapter changes create a new complete artifact even with unchanged job code.

No Python-to-C#-to-Java conversion chain is used. Original source DDL, not SQLite
introspection, carries decimal precision, field widths, nullable requirements,
source integer bounds and primary keys. No capability gap is erased by DDL emission.

Immutable paths: output/PROCESS/targets/LANGUAGE-DATABASE/ARTIFACT_ID.
Run history: output/PROCESS/target_registry.json plus checksum.
Run evidence: output/PROCESS/runs/RUN_ID. Current single report is at process root.
Caches: configured cache/retarget-v2/models and /code, each with content seals.
A shared-store lock prevents concurrent cache publication. After an interrupted
run, verify the recorded PID before deleting a stale lock; stale-lock removal is
not automatic. The model/language cache resumes work; a business process always
starts with fresh test state, not partial database changes from an interrupted run.

The v1 compatibility runner remains only for the inherited regression tests and
its legacy registration entry point. The public demo/run/init commands use v2.
Agent-native registrations have separate target/source-bound identities and
explicit review metadata. Agent reuse suggestions are hints, not validation proof.
