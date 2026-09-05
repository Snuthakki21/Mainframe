"""Compile and test execution copies; never change a sealed candidate or baseline.

Real database execution and contract recording are deliberately different results.
Recording checks file behavior and ordered INSERT/COMMIT/ROLLBACK requests by
replaying those requests in a disposable reference SQLite database. It does not
exercise a remote adapter, a JDBC driver, or the selected database's semantics.
"""
from __future__ import annotations
from contextlib import closing
from pathlib import Path
import copy,json,os,shutil,sqlite3,subprocess,sys
from migration.common import Blocked,inside,read_json,write_json,atomic_write
from migration.runner import _compare_file,_compare_db,_path
from .schema import ddl


def _command(args,cwd,log,timeout=120,env=None):
    """Capture the actual tool command and output; do not install anything or retry."""
    try:
        p=subprocess.run([str(a) for a in args],cwd=cwd,capture_output=True,text=True,
                         encoding='utf-8',errors='replace',timeout=timeout,env=env)
        record={'command':[str(a) for a in args],'exit_code':p.returncode,
                'stdout':p.stdout,'stderr':p.stderr}
    except (OSError,subprocess.TimeoutExpired) as exc:
        record={'command':[str(a) for a in args],'exit_code':None,'error':str(exc)}
    write_json(log,record);return record


def _prepare_database(path,schema,initial):
    """Create a new local test database from source schema, never from a prior run."""
    if path.exists():raise Blocked('Verification database already exists; do not append to an earlier run.','TEST_ISOLATION')
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(ddl(schema,'sqlite'))
        if initial:conn.executescript(initial.read_text(encoding='utf-8-sig'))
        conn.commit()


def _replay_operations(db_path,operations):
    """Check transaction intent, not remote database execution; uncommitted work rolls back."""
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            for event in operations:
                op=event['op']
                if op=='insert':
                    table=event['table'];columns=event['columns']
                    # Identifiers came from the validated source schema; quote them again.
                    quoted=lambda name:'"'+name.replace('"','""')+'"'
                    conn.execute('INSERT INTO '+quoted(table)+' ('+','.join(map(quoted,columns))+') VALUES ('+','.join('?' for _ in columns)+')',event['values'])
                elif op=='commit':conn.commit()
                elif op=='rollback':conn.rollback()
                else:raise Blocked('Unknown recorded database operation: '+op,'CONTRACT_OPERATION')
        finally:conn.rollback()


def verify_target(artifact,folder,cfg,paths,payload,target,baseline_ok,contract_only=False):
    """Return measured evidence for this exact language/database artifact and test run."""
    artifact,folder=Path(artifact),Path(folder);folder.mkdir(parents=True,exist_ok=False)
    code=folder/'execution-copy';shutil.copytree(artifact,code)
    result={'generation':'PASSED','compilation':'NOT_RUN','native_database':'NOT_RUN',
            'contract_execution':'NOT_RUN','baseline_kind':cfg['baseline']['kind'],
            'cases':[],'failed':False,'detail':'','compilation_evidence':None}
    language=target['language'];database=target['database'];launcher=[]
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    if language=='python':
        try:
            sources=list(code.rglob('*.py'))
            for p in sources:compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
            result['compilation']='PASSED';result['compilation_evidence']={'tool':'Python compile','files':len(sources),'version':sys.version}
            launcher=[sys.executable,'-B',str(code/'_entry.py')]
        except SyntaxError as exc:
            result.update(compilation='FAILED',failed=True,detail=str(exc))
    elif language=='java':
        javac=shutil.which('javac');java=shutil.which('java')
        if not javac or not java:
            result.update(compilation='NOT_AVAILABLE',detail='A matching approved JDK is not installed. Native Java code was generated but not compiled.')
        else:
            build=code/'build';build.mkdir()
            outcome=_command([javac,'--release',str(target['versions']['java_release']),'-d',build]+sorted(code.rglob('*.java')),code,folder/'compile.json')
            result['compilation_evidence']=outcome
            result['compilation']='PASSED' if outcome['exit_code']==0 else 'FAILED'
            result['failed']=outcome['exit_code']!=0
            cp=str(build)+(os.pathsep+env['MIGRATION_JAVA_CLASSPATH'] if env.get('MIGRATION_JAVA_CLASSPATH') else '')
            launcher=[java,'-cp',cp,'Main']
    elif language=='dotnet':
        dotnet=shutil.which('dotnet')
        if not dotnet:
            result.update(compilation='NOT_AVAILABLE',detail='.NET SDK is not installed. C# generation is not a native compilation or execution pass.')
        else:
            # Compile the dependency-free recording route. Real providers require
            # approved package restore, a transitive lock, and separate DB tests.
            restore=_command([dotnet,'restore',code/'MigratedProcess.csproj','--configfile',code/'NuGet.Config',
                              '-p:IncludeDatabaseDrivers=false'],code,folder/'restore.json')
            outcome=restore
            if restore['exit_code']==0:
                outcome=_command([dotnet,'build',code/'MigratedProcess.csproj','--configuration','Release',
                                  '--no-restore','-p:IncludeDatabaseDrivers=false'],code,folder/'compile.json')
            result['compilation_evidence']={'restore':restore,'build':outcome if restore['exit_code']==0 else 'NOT_RUN'}
            result['compilation']='PASSED' if outcome['exit_code']==0 else 'FAILED'
            result['failed']=outcome['exit_code']!=0
            launcher=[dotnet,str(code/'bin'/'Release'/target['versions']['dotnet_framework']/'MigratedProcess.dll')]
    if result['compilation']!='PASSED':
        result['native_database']='NOT_RUN_NO_RUNTIME';write_json(folder/'verification.json',result);return result
    if not baseline_ok:
        result.update(native_database='NOT_RUN_NO_BASELINE',detail='Generated code was compiled; no comparison was performed without complete frozen evidence.')
        write_json(folder/'verification.json',result);return result
    native=(language=='python' and database=='sqlite' and not contract_only)
    # Java SQLite is truly native only with an explicitly supplied driver classpath.
    if language=='java' and database=='sqlite' and env.get('MIGRATION_JAVA_CLASSPATH') and not contract_only:native=True
    mode='native_sqlite' if native else 'contract_recording'
    if native:result['detail']='Files, return codes and a fresh actual SQLite database were compared with the supplied baseline.'
    else:
        result['native_database']='NOT_RUN_REMOTE' if database!='sqlite' else 'NOT_RUN_DRIVER_NOT_TESTED'
        result['detail']='Explicit contract recording: files and transaction-request intent are checked; the selected database/driver is not executed. No remote service was contacted.'
    for case in cfg['cases']:
        work=folder/'cases'/case['name'];work.mkdir(parents=True,exist_ok=False)
        root=_path(paths['base'],case['path']);db_path=work/'local.sqlite'
        initial=inside(root,case['initial_database']) if case.get('initial_database') else None
        _prepare_database(db_path,payload['schema'],initial)
        item={'name':case['name'],'mode':mode,'file_passed':0,'file_total':0,'database_passed':0,'database_total':0,'rc_passed':0,'rc_total':0,'status':'PASSED','checks':[],'jobs':[]}
        ctx={**copy.deepcopy(payload),'case_root':str(root),'work_root':str(work),'database_path':str(db_path),
             'execution_mode':'native' if native else 'contract','allow_remote':False}
        aborted=False
        for job in cfg['execution_order']:
            ctx['job']=job;context_path=work/(job+'-context.json');job_result=work/(job+'-result.json');write_json(context_path,ctx)
            outcome=_command(launcher+[job,str(context_path),str(job_result)],code,work/(job+'-execution.json'),cfg.get('timeout_seconds',30),env)
            observed=read_json(job_result) if job_result.exists() else {'status':'FAILED','error':'The process did not create a result.'}
            item['jobs'].append({'job':job,'process_exit':outcome['exit_code'],**observed})
            expected_rc=case.get('return_codes',{}).get(job)
            if expected_rc is not None:
                item['rc_total']+=1
                okay=outcome['exit_code']==0 and observed.get('status')=='PASSED' and observed.get('return_code')==expected_rc
                item['rc_passed']+=int(okay)
                item['checks'].append({'kind':'return_code','name':job,'status':'PASSED' if okay else 'FAILED','expected':expected_rc,'observed':observed.get('return_code')})
            if outcome['exit_code']!=0 or observed.get('status')!='PASSED':
                item['status']='FAILED';aborted=True;break
            if not native:
                try:_replay_operations(db_path,observed.get('operations',[]))
                except Exception as exc:
                    item['checks'].append({'kind':'contract_replay','status':'FAILED','detail':str(exc)});item['status']='FAILED';aborted=True;break
        for dsn,expected_path in case.get('expected_files',{}).items():
            check=_compare_file(inside(work,cfg['datasets'][dsn]['path']),inside(root,expected_path),dsn)
            item['checks'].append(check);item['file_total']+=1;item['file_passed']+=int(check['status']=='PASSED')
        if case.get('expected_database'):
            for check in _compare_db(db_path,inside(root,case['expected_database'])):
                if not native:check['kind']='transaction_intent_replay';check['detail']='Not a target DB test. '+check.get('detail','')
                item['checks'].append(check);item['database_total']+=1;item['database_passed']+=int(check['status']=='PASSED')
        if aborted or any(c['status']=='FAILED' for c in item['checks']):item['status']='FAILED';result['failed']=True
        result['cases'].append(item)
    mapped={(m['job'],x['id']) for m in payload['models'] for x in m.get('trace',{}).get('statements',[])}
    visited={(j['job'],sid) for c in result['cases'] for j in c['jobs'] for sid,count in j.get('events',{}).items() if count>0}
    result['statement_evidence']={'mapped':len(mapped),'exercised':len(mapped&visited),
                                  'not_exercised':sorted([list(x) for x in mapped-visited]),
                                  'meaning':'Observed mapped statements only, not complete branch/path coverage or business-rule completeness.'}
    status='FAILED' if result['failed'] else 'PASSED'
    result['native_database' if native else 'contract_execution']=status
    write_json(folder/'verification.json',result);return result
