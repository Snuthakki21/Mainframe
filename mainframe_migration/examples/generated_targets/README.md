# Generated reference targets — not an active cache

These nine complete source packages were freshly generated from the bundled synthetic
COBOL/JCL fixture by the v2 emitters. They are included so you can inspect the native
jobs, runtime, selected database adapter, logical schema, target DDL and dependencies.
They are not consulted by the generator or tests: the exact-ZIP exercise creates new
artifacts from the original sample sources in a separate working folder.

All nine selections generated. Python and Java execution evidence is described in
the release verification report; .NET was not compiled here. Only Python/SQLite had
native database execution. Recording tests do not establish Oracle, BigQuery or JDBC
provider correctness. BigQuery packages retain an explicit primary-key capability
blocker. Do not deploy these synthetic examples or use their generation seals as
production approval. No credentials or binary database drivers are included.
