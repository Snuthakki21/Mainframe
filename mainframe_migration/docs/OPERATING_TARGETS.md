# Build and execution details

Normal operators choose target.json and use the one kickoff. These details are
for the agent/platform team; no automatic public installation is performed.

## Python

The framework and Python/SQLite need standard library only. Oracle uses the exact
oracledb version declared in target.json. Resolve it through the configured
Artifactory pip index, then capture a hash-locked approved dependency set. BigQuery
uses the documented REST Jobs API and an externally supplied short-lived bearer
token; refresh and credentials management are not implemented inside the adapter.

## Java

Generation emits native .java jobs and a shared native runtime, not Python wrappers.
An installed approved JDK compiles against `versions.java_release`. SQLite needs
org.xerial:sqlite-jdbc and its transitive dependencies; Oracle needs ojdbc11.
Dependencies and versions are in dependencies.json. Resolve through Artifactory,
verify/lock them, and provide the local classpath:

```powershell
$env:MIGRATION_JAVA_CLASSPATH = "C:\approved-drivers\*"
python modernize.py run --config "processes/PAYMENTS/process.json"
```

When no classpath is supplied, Java/SQLite is tested only in explicit transaction
recording mode. If a supplied driver fails to load, the native execution fails;
it does not silently fall back. BigQuery uses Java HttpClient, not JDBC.

## C# / .NET

Generation emits native C# jobs and a complete project targeting the configured
framework. SDK absence is NOT_AVAILABLE. The local verifier restores only the
dependency-free recording build using an empty NuGet source list, then builds with
--no-restore. It does not download a target SDK or database provider.

For a real selected-provider build, use an execution copy of the sealed artifact:

```powershell
dotnet restore .\MigratedProcess.csproj --source "$env:MIGRATION_NUGET_SOURCE" -p:IncludeDatabaseDrivers=true
dotnet build .\MigratedProcess.csproj --no-restore --configuration Release -p:IncludeDatabaseDrivers=true
```

MIGRATION_NUGET_SOURCE must already hold the approved Artifactory NuGet feed.
This creates the dependency lock; review and retain it. Do not insert these build
outputs into an immutable artifact directory. The local verifier's .NET route
currently runs only recording-mode tests even when providers are restored.

## Oracle / BigQuery live integration

Selected adapters contain actual binding and transaction implementations, not
unfilled stubs. They are supplied for review and integration, not claimed live
validated. Default workbench verification never contacts remote databases and
never deploys DDL. A real integration harness must provision the controlled
baseline state, enable `allow_remote` only in the execution context, run the same
jobs, capture typed final state, and compare it using approved target tooling.
Automatic remote provisioning and a live target-snapshot harness are NOT included.

The environment-variable names are in target.json. Oracle expects an Easy Connect
DSN. BigQuery expects project, dataset, location and access token. Session and job
IDs are retained before mutations; an uncertain outcome is not retried. There is
no supported override to waive an unresolved semantic capability blocker.

An Oracle/BigQuery connection string is not enough to establish behavioral
compatibility. BigQuery key enforcement and Oracle empty-string representation
are explicit review points. Storage changes and application-language changes do
not migrate physical production data or deploy the new application automatically.
