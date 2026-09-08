# Mainframe modernization

The complete framework is in [mainframe_migration](mainframe_migration/).
Start with [START_HERE.md](mainframe_migration/START_HERE.md).

Supply one Markdown (`.md`) process inventory and the local mainframe source
repository. The framework parses the documented jobs and steps, discovers source
dependencies, generates the selected language/database target through the agent
workflow, and reports execution evidence and unresolved questions.

Python, C#/.NET and Java can each target SQLite, Oracle or BigQuery. Existing
Excel inventories remain compatible. See the [Markdown input contract](mainframe_migration/docs/MARKDOWN_INPUT.md)
for the format and output locations, and the [support limits](mainframe_migration/docs/SUPPORT_AND_LIMITS.md)
for the distinction between generated artifacts and validated behavior.
