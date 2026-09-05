"""Assemble standalone native target packages from sealed behavior models.

Each target has a separate immutable artifact folder. Changing a database never
translates SQLite code into another dialect: it emits a new database adapter and
DDL from the original schema while retaining the same language-specific job code.
"""
from pathlib import Path
import json
from migration.common import Blocked,digest,fingerprint
from .emit import emit_job
from .schema import ddl,capabilities
from .model import encoding_tables
TEMPLATES=Path(__file__).parent/'templates'

EXT={'python':'.py','java':'.java','dotnet':'.cs'}

def dependency_manifest(target):
    """Declare required artifacts without automatically downloading from public feeds."""
    l,d=target['language'],target['database'];v=target['dependencies'];items=[]
    if l=='python' and d=='oracle':items=[{'manager':'pip','name':'oracledb','version':v.get('python_oracle','3.2.0')}]
    if l=='java' and d in {'sqlite','oracle'}:items=[{'manager':'maven','name':'org.xerial:sqlite-jdbc' if d=='sqlite' else 'com.oracle.database.jdbc:ojdbc11','version':v.get('java_'+d,'3.50.3.0' if d=='sqlite' else '23.9.0.25.07')}]
    if l=='dotnet' and d in {'sqlite','oracle'}:items=[{'manager':'nuget','name':'Microsoft.Data.Sqlite' if d=='sqlite' else 'Oracle.ManagedDataAccess.Core','version':v.get('dotnet_'+d,'10.0.11' if d=='sqlite' else '23.26.300')}]
    return {'dependencies':items,'source_policy':'Resolve through the approved Artifactory feed. No restore/download is performed by generation.',
            'transitive_lock_status':'NOT_RESOLVED_HERE; capture dependency lock/hashes using the approved feed before deployment.'}

def assemble(models,schema,cfg,target,job_codes=None):
    """Return the complete artifact file map, not a set of unfilled adapter stubs."""
    language,database=target['language'],target['database'];files={}
    for model in models:
        files['jobs/'+model['job']+EXT[language]] = job_codes[model['job']] if job_codes is not None else emit_job(model,language)
    if language=='python':
        for src,dst in [('runtime.py.txt','_runtime.py'),('database.py.txt','_database.py'),('common.py.txt','_common.py'),('entry.py.txt','_entry.py')]:
            files[dst]=(TEMPLATES/'python'/src).read_text().replace('@@DATABASE@@',database)
        for path,text in files.items():
            if path.endswith('.py'):compile(text,path,'exec')
    elif language=='java':
        for p in (TEMPLATES/'java').glob('*.java'):files[p.name]=p.read_text().replace('@@DATABASE@@',database)
        dispatch='\n'.join('                case "'+m['job']+'": '+m['job']+'.run(ctx); break;' for m in models)
        files['Main.java']=(TEMPLATES/'java/Main.java.txt').read_text().replace('@@DISPATCH@@',dispatch)
        files['build.cmd']='@echo off\r\ncd /d "%~dp0"\r\nif not exist build mkdir build\r\njavac --release '+str(target['versions']['java_release'])+' -d build *.java jobs\\*.java\r\nexit /b %ERRORLEVEL%\r\n'
        files['build.sh']='#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nmkdir -p build\njavac --release '+str(target['versions']['java_release'])+' -d build ./*.java jobs/*.java\n'
    else:
        for p in (TEMPLATES/'dotnet').glob('*.cs'):files[p.name]=p.read_text().replace('@@DATABASE@@',database)
        dispatch='\n'.join('            case "'+m['job']+'": '+m['job']+'.run(ctx); break;' for m in models)
        files['Main.cs']=(TEMPLATES/'dotnet/Main.cs.txt').read_text().replace('@@DISPATCH@@',dispatch)
        deps=dependency_manifest(target)['dependencies'];package=''.join('    <PackageReference Include="'+x['name']+'" Version="'+x['version']+'" />\n' for x in deps)
        files['MigratedProcess.csproj']='<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <OutputType>Exe</OutputType>\n    <TargetFramework>'+target['versions']['dotnet_framework']+'</TargetFramework>\n    <Nullable>disable</Nullable>\n    <ImplicitUsings>disable</ImplicitUsings>\n    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>\n    <IncludeDatabaseDrivers Condition="\'$(IncludeDatabaseDrivers)\' == \'\'">true</IncludeDatabaseDrivers>\n  </PropertyGroup>\n  <ItemGroup Condition="\'$(IncludeDatabaseDrivers)\' == \'true\'">\n'+package+'  </ItemGroup>\n</Project>\n'
        files['NuGet.Config']='<?xml version="1.0" encoding="utf-8"?>\n<configuration><packageSources><clear /></packageSources></configuration>\n'
    issues=capabilities(schema,database)
    package={'schema_version':2,'language':language,'database':database,'models':models,'schema':schema,'codepages':encoding_tables(cfg),
             'datasets':cfg['datasets'],'collation':cfg.get('collation','cp037'),'connections':target['connections'],
             'capability_blockers':issues,'execution_order':cfg['execution_order'],'max_sort_records':cfg.get('max_sort_records',100000)}
    files['package.json']=json.dumps(package,indent=2,ensure_ascii=True)+'\n'
    files['database/schema.sql']=ddl(schema,database)
    files['database/logical_schema.json']=json.dumps(schema,indent=2)+'\n'
    files['database/capabilities.json']=json.dumps({'status':'BLOCKED' if issues else 'NO_KNOWN_SUBSET_BLOCKER','items':issues},indent=2)+'\n'
    files['dependencies.json']=json.dumps(dependency_manifest(target),indent=2)+'\n'
    files['target.json']=json.dumps(target,indent=2)+'\n'
    files['README.md']=f'''# {language} / {database} generated artifact

This directory is an immutable generation result, not a production approval.
The same source behavior model is used for all targets. Jobs are native {language}
functions, one source file per job; they are not a wrapper around Python code.

Database schema: `database/schema.sql`. Schema requirements: `database/logical_schema.json`.
Check `database/capabilities.json` before execution. It may contain blocking
semantic differences even though code generation completed.

Dependencies are listed in `dependencies.json`. Use the approved Artifactory feed;
no public download or restore is performed by the generation workflow. Pinned
direct versions are not a full transitive dependency lock. Resolve and lock the
chosen drivers in the approved environment before deployment.

The workbench builds fresh execution copies and prepares the context JSON for
local validation. Never add build outputs or change source files in this sealed
folder. A failed candidate is reported, not automatically repaired.

Remote adapters are not exercised by local SQLite comparisons. BigQuery uses
short-lived bearer tokens supplied through the named environment variable; token
refresh and IAM setup remain external operational configuration. No automatic
DML retry is made after an uncertain remote outcome. Recorded job IDs support
manual reconciliation. Oracle expects the configured Easy Connect data source.

DDL is supplied for controlled deployment. The generated runner never creates,
drops, or resets Oracle/BigQuery objects. Local validation creates only fresh SQLite
files. Oracle/BigQuery integration needs separately provisioned test environments
and baseline evidence before it can receive a live-validation status.
'''
    if any('@@' in s for s in files.values()):raise Blocked('An unresolved generation token remains.','GENERATOR')
    return files,package
