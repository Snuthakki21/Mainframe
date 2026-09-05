# Source references for target design

Consulted during the v2 build. These references support API and semantic choices;
they do not replace execution against the target database or the bank environment.

- BigQuery transactions and session scope:
  https://docs.cloud.google.com/bigquery/docs/transactions
- BigQuery Jobs REST configuration, createSession, connectionProperties and job IDs:
  https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/Job
- Query parameter types and values:
  https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/QueryParameter
- Primary and foreign keys are not enforced:
  https://docs.cloud.google.com/bigquery/docs/primary-foreign-keys
- Oracle null and empty-string semantics:
  https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Nulls.html
- Python Oracle driver version and installation:
  https://python-oracledb.readthedocs.io/en/v3.2.0/
  https://python-oracledb.readthedocs.io/en/stable/user_guide/installation.html
- OracleDecimal precision and Parse:
  https://docs.oracle.com/en/database/oracle/oracle-database/23/odpnt/OracleDecimalStructure.html
  https://docs.oracle.com/en/database/oracle/oracle-database/23/odpnt/DecimalParse.html
- Native package declarations, not a tested dependency lock:
  https://www.nuget.org/packages/Microsoft.Data.Sqlite/10.0.11
  https://www.nuget.org/packages/Oracle.ManagedDataAccess.Core/23.26.300
  https://central.sonatype.com/artifact/com.oracle.database.jdbc/ojdbc-bom/23.9.0.25.07
- dotnet restore and build command separation:
  https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-restore
  https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-build
- Repository skill conventions (no live vendor session tested):
  https://code.visualstudio.com/docs/agent-customization/agent-skills
  https://docs.devin.ai/product-guides/skills

Context7 was used for BigQuery session API documentation. Superpowers methods
informed planning, failing/passing regression checks and evidence-based review;
neither plugin is a runtime dependency of this package.
