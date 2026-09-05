# Retargeting implementation and verification plan

Goal: make language and database independent, explicit choices while retaining source behavior and immutable evidence.
Architecture: the existing source front end builds a versioned portable behavior model. Native Python, Java and C# emitters generate one file per job. A separate schema/database layer emits SQLite, Oracle and BigQuery components. Target-specific status never inherits validation from another target.

## Constraints
No changes to source business rules or frozen expectations. No Git operations or automatic candidate repair. Do not execute against a remote database as part of generation. No public package downloads in the shipped runner. Standard-library Python verification remains available on Windows.

## Tasks and acceptance checks
1. Add target.json; reject unknown keys, languages and ambiguous GCP targets. Test normalization, duplicate JSON keys, and unsupported runtime versions.
2. Extract and seal per-job behavior models using source/dependency hashes. Test changing only the database reuses analysis and job code; changing language reuses analysis, not language artifacts.
3. Preserve source integer bounds, CHAR/VARCHAR distinction, decimal scale, nullability and primary keys. Test all three DDL dialects and explicit BigQuery primary-key capability blockers.
4. Generate native job functions from the same model for all three languages. No Python subprocess may appear in Java or C# job implementations.
5. Supply real database adapters, explicit transaction boundaries, bound values, exact numeric handling, and no network action in generation. Verify adapter contracts separately from live database behavior.
6. Seal all emitted artifacts and target descriptors. Test tampered models, altered generated files, concurrent locks, output collisions, and history integrity.
7. Execute available runtimes with the same sample inputs and compare independently frozen outputs. Distinguish real SQLite results, contract traces, compilation, and unavailable external runtimes.
8. Run all legacy regressions, new adversarial tests, a nine-target matrix, and a second-run reuse check. Package, extract the final ZIP into a path with spaces, and repeat the verification there.
9. Update the single report, skill, start guide, support matrix and PowerPoint. Record unresolved review findings and exact environment rather than production-certifying unexecuted targets.
