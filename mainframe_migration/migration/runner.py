"""One-command local orchestration, with honest stop conditions.

The same runner discovers, generates (or reuses a sealed agent artifact), executes,
and compares a process. Each test starts in a fresh run directory and SQLite file.
Unexpected source behavior is not repaired. Unknowns become one report queue.
No Git, network, model API, installation, or business-code repair is performed.
"""
from __future__ import annotations
import ast
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import codecs
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from .common import Blocked,atomic_write,changed,digest,fingerprint,inside,read_json,snapshot,write_json
from .compiler import compile_job,translate_ddl
from .discovery import discover
from .inventory import read_inventory
from .process_flow import normalize_flow
from .report import write_report

ROOT=Path(__file__).resolve().parents[1]
LIMITATIONS=[
 'This release includes a bounded offline COBOL/JCL translator and an agent-artifact handoff. It is not a universal COBOL or z/OS compiler.',
 'Synthetic baseline results are not IBM mainframe equivalence. Supply captured mainframe outputs and initial database state for the real process.',
 'The actual Windows laptop, Copilot agent, and Devin agent were not exercised in this development environment.',
 'Db2 SQLCODE/SQLSTATE handling, isolation/locking, triggers, complex DDL, CICS/IMS, VSAM, GDGs, PROC expansion and scheduler behavior require source-specific agent work and validation.',
 'Oracle and BigQuery adapters/DDL are not delivered as validated targets. SQLite is the implemented local target.',
 'Generated-code path checks and subprocess timeouts are not an operating-system sandbox.',
 'AI credit counts are unavailable to this local runner. Hash-based reuse avoids repeated generation work but cannot enforce an IDE provider token budget.'
]

def _path(base: Path,value: str) -> Path:
    p=Path(value);return p.resolve() if p.is_absolute() else (base/p).resolve()

def tool_fingerprint() -> str:
    """Invalidate cached code whenever compiler/runtime/instructions change."""
    files=list((ROOT/'migration').glob('*.py'))+[ROOT/'modernize.py',ROOT/'AGENTS.md',ROOT/'.agents/skills/migrate-process/SKILL.md']
    return fingerprint({str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in files if p.exists()})

def load_config(path: Path) -> tuple[dict,dict]:
    cfg=read_json(path);base=path.resolve().parent
    if not isinstance(cfg,dict) or cfg.get('schema_version')!=1:raise Blocked('Use a process configuration with schema_version 1.','CONFIG')
    required={'process','repository','inventory','source_format','datasets','cases','execution_order','order_evidence','baseline'}
    missing=required-set(cfg)
    if missing:raise Blocked('The process configuration needs: '+', '.join(sorted(missing))+'. The agent should derive what it can and ask only for missing evidence.','CONFIG')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',cfg['process']):raise Blocked('Use a process name containing only letters, numbers, underscore, or hyphen.','CONFIG')
    if cfg.get('generation_mode','agent') not in {'agent','offline_subset'}:
        raise Blocked('generation_mode must be agent or offline_subset.','CONFIG')
    if cfg.get('generation_mode','agent')=='offline_subset' and cfg['baseline'].get('kind')!='synthetic':
        raise Blocked('The offline translator is a synthetic acceptance-test backend. Use agent generation for real mainframe migration.','CONFIG')
    paths={
      'repo':_path(base,cfg['repository']),'inventory':_path(base,cfg['inventory']),
      'output':_path(base,cfg.get('output','output')),'cache':_path(base,cfg.get('cache','.migration/cache')),
      'knowledge':_path(base,cfg.get('knowledge','knowledge/answers.json')),
      'agents':_path(base,cfg.get('agent_artifacts','agent_artifacts')),'base':base}
    if not paths['repo'].is_dir():raise Blocked('The local source repository folder is missing. No Git clone/pull is performed.','CONFIG')
    for write in ('output','cache','agents'):
        if paths[write]==paths['repo'] or paths['repo'].is_relative_to(paths[write]):
            raise Blocked(f'{write} must not equal or contain the source repository.','UNSAFE_PATH')
    for name,spec in cfg['datasets'].items():
        if spec.get('role') not in {'input','output','intermediate'}:raise Blocked(f'{name} needs an explicit input/output/intermediate role.','DATASET_BINDING')
        if spec.get('format')!='fixed':raise Blocked(f'{name}: only explicit fixed records are implemented offline.','AGENT_REQUIRED')
        if not isinstance(spec.get('record_length'),int) or not 1<=spec['record_length']<=32760:raise Blocked(f'{name} needs a fixed record length from its authoritative definition.','DATASET_BINDING')
        if not spec.get('encoding'):raise Blocked(f'{name} needs its actual encoding; do not guess ASCII or EBCDIC.','DATASET_BINDING')
        codecs.lookup(spec['encoding']);inside(paths['base'],spec['path'])
    if len({(s['role']=='input',s['path']) for s in cfg['datasets'].values()}) != len(cfg['datasets']):
        raise Blocked('Two dataset bindings alias the same local path. Resolve their lifecycle explicitly.','DATASET_BINDING')
    if len(cfg['execution_order'])!=len(set(cfg['execution_order'])):raise Blocked('execution_order contains a duplicate job.','PROCESS_ORDER')
    names=[c['name'] for c in cfg['cases']]
    if len(set(names))!=len(names) or any(not re.fullmatch(r'[A-Za-z0-9_-]+',n) for n in names):raise Blocked('Test case names must be unique path-safe names.','CONFIG')
    if not 1<=int(cfg.get('timeout_seconds',60))<=3600:raise Blocked('timeout_seconds must be between 1 and 3600.','CONFIG')
    return cfg,paths

def knowledge(path: Path, process: str) -> tuple[list, list]:
    """Only approved, scoped answers apply; drafts never become global rules."""
    if not path.exists():return [],[]
    data=read_json(path)
    if data.get('schema_version')!=1 or not isinstance(data.get('answers'),list):raise Blocked('Knowledge file needs schema_version 1 and an answers list.','KNOWLEDGE')
    approved=[];seen={}
    for answer in data['answers']:
        if answer.get('status')!='approved':continue
        required={'id','scope','answer','approved_by','evidence'}
        if required-set(answer) or not all(answer[k] for k in required):raise Blocked('An approved answer is missing its ID, scope, answer, approver, or evidence.','KNOWLEDGE')
        scope=answer['scope']
        if scope not in {process,'global'}:continue
        identity=(answer['id'],scope)
        if identity in seen and seen[identity]!=answer['answer']:raise Blocked(f'Conflicting approved answers for {answer["id"]}. Resolve the conflict; do not pick one silently.','KNOWLEDGE')
        seen[identity]=answer['answer'];approved.append(answer)
    return approved,data['answers']

def inspect_python(text: str, name: str) -> None:
    """Check the executable contract, not whether an AI's explanation sounds confident."""
    if re.search(r'\b(?:TODO|FIXME|NotImplementedError)\b',text):raise Blocked('Generated code contains an unfinished implementation marker.','GENERATED_CODE',name)
    try:tree=ast.parse(text,filename=name)
    except SyntaxError as exc:raise Blocked(f'Generated Python does not compile: {exc}. No repair is performed.','GENERATED_CODE',name) from exc
    run=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='run']
    if len(run)!=1 or not isinstance(run[0],ast.FunctionDef) or len(run[0].args.args)!=1:
        raise Blocked('The job file needs one synchronous run(ctx) entry point.','GENERATED_CODE',name)
    if not ast.get_docstring(tree):raise Blocked('The job file needs a plain-English purpose/source header.','GENERATED_CODE',name)
    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and not ast.get_docstring(n):raise Blocked(f'Function {n.name} needs a plain-English intent comment/docstring.','GENERATED_CODE',name)

def _compare_file(actual: Path, expected: Path, name: str) -> dict:
    """Compare exact bytes: no whitespace trimming, tolerance, sorting, or deduplication."""
    result={'kind':'file','name':name,'status':'FAILED'}
    if not actual.exists():result['detail']='Expected output was not created.';return result
    if not expected.exists():result['detail']='Authoritative expected output is missing.';return result
    a,e=actual.read_bytes(),expected.read_bytes()
    result['actual_sha256']=digest(a);result['expected_sha256']=digest(e)
    if a==e:result.update(status='PASSED',detail=f'Exact bytes match ({len(a)} bytes).')
    else:
        first=next((i for i,(x,y) in enumerate(zip(a,e)) if x!=y),min(len(a),len(e)))
        result['detail']=f'Byte mismatch at offset {first}; actual length {len(a)}, expected {len(e)}. No bytes were normalized.'
    return result

def _compare_db(path: Path, expected: Path) -> list[dict]:
    """Compare typed row multisets, including duplicate counts; tables have no row order."""
    baseline=read_json(expected)
    result=[]
    with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)) as conn:
        actual_tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if actual_tables != set(baseline):
            result.append({'kind':'database','name':'table inventory','status':'FAILED','detail':f'Actual table set {sorted(actual_tables)} differs from expected {sorted(baseline)}.'})
        for table,spec in baseline.items():
            if not re.fullmatch(r'[A-Z][A-Z0-9_]*',table):raise Blocked('Expected table name is not a supported SQL identifier.','TEST_EVIDENCE')
            item={'kind':'database','name':table,'status':'FAILED'}
            cols=spec['columns']
            if not all(re.fullmatch(r'[A-Z][A-Z0-9_]*',c) for c in cols):raise Blocked('Expected database columns contain an unsafe identifier.','TEST_EVIDENCE')
            real=[r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            if real!=cols:item['detail']='Database column names/order do not match the expected table definition.';result.append(item);continue
            query='SELECT '+','.join('"'+c+'"' for c in cols)+f' FROM "{table}"'
            actual=[list(r) for r in conn.execute(query)]
            canonical=lambda rows:Counter(json.dumps(r,separators=(',',':'),ensure_ascii=True) for r in rows)
            if canonical(actual)==canonical(spec['rows']):item.update(status='PASSED',detail=f'{len(actual)} typed rows match, including duplicate counts.')
            else:item['detail']=f'Typed row mismatch: actual {len(actual)} rows, expected {len(spec["rows"])}. No target/expected rows were changed.'
            result.append(item)
    return result

def _baseline_files(cfg: dict,paths: dict) -> list[Path]:
    files=[]
    for case in cfg['cases']:
        root=_path(paths['base'],case['path'])
        for spec in cfg['datasets'].values():
            if spec['role']=='input':files.append(inside(root,spec['path']))
        files += [inside(root,f) for f in case.get('expected_files',{}).values()]
        for name in ('initial_database','expected_database'):
            if case.get(name):files.append(inside(root,case[name]))
    return files

def _check_baseline(cfg: dict,paths: dict) -> None:
    baseline=cfg['baseline']
    if not cfg['cases']:
        raise Blocked('Test evidence is not available yet. Supply matched inputs, expected outputs/database state, business-date/control values, and mainframe run/source provenance. Discovery will still continue.','TEST_EVIDENCE')
    if baseline.get('kind') not in {'synthetic','mainframe'}:raise Blocked('Label baseline.kind as synthetic or mainframe.','TEST_EVIDENCE')
    if baseline['kind']=='mainframe' and not all(baseline.get(k) for k in ('run_id','source_revision','runtime_context')):
        raise Blocked('A mainframe baseline needs its run ID, source revision, and runtime context (business date, controls, and initial database state).','TEST_EVIDENCE')
    if not baseline.get('manifest'):raise Blocked('Provide a frozen baseline SHA-256 manifest. The migration agent must not invent expected outputs.','TEST_EVIDENCE')
    manifest_path=_path(paths['base'],baseline['manifest']);manifest=read_json(manifest_path)
    protected=_baseline_files(cfg,paths)
    for p in protected:
        try:relative=p.relative_to(paths['base']).as_posix()
        except ValueError:raise Blocked('Test-case files must be underneath the process configuration folder for baseline verification.','TEST_EVIDENCE')
        if not p.is_file() or manifest.get(relative)!=digest(p.read_bytes()):
            raise Blocked(f'Test evidence {relative} is missing or differs from the frozen manifest. Restore the supplied evidence or have its owner provide a new baseline; do not adjust it to make a test pass.','BASELINE_INTEGRITY',relative)
    outputs={name for name,spec in cfg['datasets'].items() if spec['role']!='input'}
    for case in cfg['cases']:
        if cfg['baseline']['kind']=='mainframe' and set(case.get('return_codes',{}))!=set(cfg['execution_order']):
            raise Blocked(f'Case {case["name"]} needs the captured return code for every selected job.','TEST_EVIDENCE')
        if any(type(rc) is not int for rc in case.get('return_codes',{}).values()):
            raise Blocked('Expected job return codes must be integers.','TEST_EVIDENCE')
        if set(case.get('expected_files',{}))!=outputs:
            raise Blocked(f'Case {case["name"]} must account for every output/intermediate dataset; missing or additional baseline mappings cannot be ignored.','TEST_EVIDENCE')

def _key(job: dict,discovery: dict,cfg: dict,answers: list,tool_hash: str,ddl_hash: str) -> str:
    return fingerprint({'job':job,'sources':{p:discovery['sources'][p] for p in job['dependencies']},
       'ddl':ddl_hash,'answers':answers,'tools':tool_hash,'format':cfg['source_format'],'collation':cfg.get('collation'),
       'datasets':cfg['datasets'],'generation_mode':cfg.get('generation_mode','agent'),'agent_generation_version':cfg.get('agent_generation_version',1)})

def _seal_cache(target: Path,code: str,trace: dict,key: str) -> None:
    target.mkdir(parents=True,exist_ok=True)
    atomic_write(target/'job.py',code)
    write_json(target/'manifest.json',{'fingerprint':key,'code_sha256':digest(code.encode()),'trace_sha256':fingerprint(trace),'trace':trace})

def _load_sealed(target: Path,key: str) -> tuple[str,dict]:
    meta=read_json(target/'manifest.json');code=(target/'job.py').read_text(encoding='utf-8')
    if meta.get('fingerprint')!=key or digest(code.encode())!=meta.get('code_sha256') or fingerprint(meta['trace'])!=meta.get('trace_sha256'):
        raise Blocked('A cached/sealed artifact has changed. It will not be repaired or silently regenerated. Quarantine it and investigate.','CACHE_INTEGRITY',str(target))
    inspect_python(code,'job.py');return code,meta['trace']

def run(config_path: Path,output_override: Path | None = None,discover_only: bool = False) -> dict:
    """Complete every safe stage from one invocation; always leave one readable report."""
    cfg,paths={},{}
    try:
        cfg,paths=load_config(config_path)
        if output_override:paths['output']=output_override.resolve()
    except Exception as exc:
        e=exc if isinstance(exc,Blocked) else Blocked(str(exc),'CONFIG')
        folder=(output_override or ROOT/'output').resolve()/('setup-'+uuid.uuid4().hex[:10]);folder.mkdir(parents=True)
        result={'process':'configuration','status':'BLOCKED','issues':[e.issue()],'limitations':LIMITATIONS,'environment':platform.platform(),'stages':[],'metrics':{}}
        write_json(folder/'result.json',result);write_report(folder,result);result['report']=str(folder/'modernization_report.html');return result
    folder=paths['output']/cfg['process']/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True,exist_ok=False)
    result={'process':cfg['process'],'status':'INCOMPLETE','environment':platform.platform()+' / Python '+platform.python_version(),
       'baseline':cfg['baseline'].get('kind','unknown')+' — '+cfg['baseline'].get('description',''),
       'jobs':[],'cases':[],'issues':[],'review':[],'stages':[],'limitations':LIMITATIONS,
       'metrics':{'jobs_generated':0,'jobs_discovered':0,'cases_passed':0,'cases_planned':len(cfg['cases']),'cache_hits':0,'new_generations':0}}
    def stage(name,detail):
        print(f'[{name}] {detail}',flush=True);result['stages'].append({'stage':name,'detail':detail})
        write_json(folder/'result.json',result)
    lock=paths['output']/('.lock-'+cfg['process']);owned=False;before={}
    try:
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            with os.fdopen(fd,'w') as f:f.write(json.dumps({'pid':os.getpid(),'run':str(folder)}))
            owned=True
        except FileExistsError:raise Blocked('Another run holds this process lock. Check the named run/PID before removing a stale lock; concurrent execution is not allowed.','RUN_LOCK',str(lock))
        stage('CHECK','Checking configuration, baseline integrity, and local Python/SQLite access.')
        try:
            _check_baseline(cfg,paths)
        except Exception as exc:
            problem=exc if isinstance(exc,Blocked) else Blocked(str(exc),'TEST_EVIDENCE')
            result['issues'].append(problem.issue())
        if not cfg['order_evidence']:
            result['issues'].append(Blocked('Provide the evidence for inter-job execution order (scheduler export or confirmed sequence). Document order is used for discovery only, not assumed to be executable order.','PROCESS_ORDER').issue())
        answers,_=knowledge(paths['knowledge'],cfg['process']);result['metrics']['knowledge_answers']=len(answers)
        stage('DISCOVER','Reading the process inventory and following JCL, COPY, CALL, and database references.')
        rows=read_inventory(paths['inventory'],cfg.get('sheet','Process'))
        discovered=discover(paths['repo'],rows,cfg)
        result['process_flow']=normalize_flow(rows,cfg,paths['inventory'],discovered)
        result['process_flow_file']=str(folder/'process_flow.json')
        write_json(folder/'process_flow.json',result['process_flow'])
        result['issues']+=discovered['issues']
        write_json(folder/'discovery.json',{k:v for k,v in discovered.items() if k!='index'})
        names=[j['name'] for j in discovered['jobs']]
        inventory_names=list(dict.fromkeys(r['job'] for r in rows))
        if set(cfg['execution_order'])!=set(inventory_names):raise Blocked('Execution order does not name each inventory job exactly once.','PROCESS_ORDER')
        jobs=sorted(discovered['jobs'],key=lambda j:cfg['execution_order'].index(j['name']))
        result['metrics'].update(jobs_discovered=len(inventory_names),steps=sum(len(j['steps']) for j in jobs))
        ddl_parts=[];schema={};ddl_paths=[]
        ddl_names=list(cfg.get('ddl_sources',[]))
        if not ddl_names:
            needed={e['to'] for e in discovered['edges'] if e['kind']=='SQL_TABLE_CANDIDATE'}
            for members in discovered['index'].values():
                for candidate in members:
                    if candidate.suffix.lower() not in {'.sql','.ddl'}:continue
                    content=candidate.read_text(encoding='utf-8-sig')
                    tables={m.upper() for m in re.findall(r'CREATE\s+TABLE\s+([A-Z][A-Z0-9_.]*)',content,re.I)}
                    if needed&tables:ddl_names.append(candidate.relative_to(paths['repo']).as_posix())
        for name in dict.fromkeys(ddl_names):
            path=inside(paths['repo'],name)
            if not path.is_file():raise Blocked(f'Database definition {name} is missing.','MISSING_DDL',name)
            sql,part=translate_ddl(path.read_text(encoding='utf-8-sig'))
            if set(part)&set(schema):raise Blocked('Duplicate table definitions exist across DDL files.','DDL')
            schema.update(part);ddl_parts.append(sql);ddl_paths.append(path)
            discovered['sources'][str(path.relative_to(paths['repo']))]=digest(path.read_bytes())
        local_sql='\n'.join(ddl_parts) if ddl_parts else '-- This process has no configured database tables.\n'
        discovered['schema']=schema
        result['process_flow']=normalize_flow(rows,cfg,paths['inventory'],discovered)
        write_json(folder/'process_flow.json',result['process_flow'])
        for edge in discovered['edges']:
            if edge['kind']=='SQL_TABLE_CANDIDATE' and edge['to'] not in schema:
                result['issues'].append(Blocked(f'{edge["from"]} references database object {edge["to"]}. Provide its authoritative DDL and initial state; a schema will not be invented.','MISSING_DDL',edge['from']).issue())
        # A DD binding must exist even when a source program has not yet been translated.
        for job in jobs:
            for step in job['steps']:
                for dd,spec in step['dds'].items():
                    if 'dsn' in spec and spec['dsn'] not in cfg['datasets']:
                        result['issues'].append(Blocked(f'{job["name"]}/{step["name"]} DD {dd} uses {spec["dsn"]}. Supply its file role, record length, encoding, and local test location.','DATASET_BINDING',job['source']).issue(job['name']))
        stage('SCHEMA','Writing evidence-backed SQLite DDL and a portable logical schema; no unvalidated target stubs.')
        atomic_write(folder/'ddl/local.sql',local_sql);write_json(folder/'ddl/logical_schema.json',schema)
        safe_discovery={k:v for k,v in discovered.items() if k!='index'}
        write_json(folder/'discovery.json',safe_discovery)
        result['metrics']['source_members']=len(discovered['sources'])
        protected=[paths['repo']/name for name in discovered['sources']]+_baseline_files(cfg,paths)+[paths['inventory'],config_path]
        protected+=list((ROOT/'migration').glob('*.py'))+[ROOT/'modernize.py']
        if cfg['baseline'].get('manifest'):protected.append(_path(paths['base'],cfg['baseline']['manifest']))
        if paths['knowledge'].exists():protected.append(paths['knowledge'])
        before=snapshot(protected);write_json(folder/'protected_hashes.json',before)
        toolhash=tool_fingerprint();keys={};tasks=[]
        generation_soft={'TEST_EVIDENCE','PROCESS_ORDER','DATASET_BINDING'}
        nonlocal_issues=[q for q in result['issues'] if not q.get('job') and q['code'] not in generation_soft]
        for job in jobs:
            key=_key(job,discovered,cfg,answers,toolhash,digest(local_sql.encode()));keys[job['name']]=key
            item={'name':job['name'],'status':'BLOCKED','mode':'not generated','statement_count':0}
            result['jobs'].append(item)
            if nonlocal_issues or any(q.get('job')==job['name'] and q['code'] not in generation_soft for q in result['issues']):continue
            if discover_only:continue
            try:
                sealed=paths['agents']/key
                cached=paths['cache']/key
                if sealed.exists():code,trace=_load_sealed(sealed,key);item['mode']='sealed agent artifact';result['metrics']['cache_hits']+=1
                elif cached.exists():code,trace=_load_sealed(cached,key);item['mode']='reused offline generation';result['metrics']['cache_hits']+=1
                else:
                    if cfg.get('generation_mode','agent') == 'agent':
                        raise Blocked('Generate this job from its source using the approved Copilot/Devin workflow. No offline translation is substituted for agent work.','AGENT_REQUIRED',job['source'])
                    code,trace=compile_job(job,discovered['index'],cfg['source_format'])
                    inspect_python(code,job['name']+'.py');_seal_cache(cached,code,trace,key)
                    item['mode']='new offline source generation';result['metrics']['new_generations']+=1
                atomic_write(folder/'code'/f'{job["name"]}.py',code)
                write_json(folder/'code'/f'{job["name"]}.trace.json',trace)
                item.update(status='GENERATED',artifact=f'code/{job["name"]}.py',statement_count=len(trace.get('statements',[])))
                result['metrics']['jobs_generated']+=1
            except Blocked as e:
                result['issues'].append(e.issue(job['name']))
                if e.code=='AGENT_REQUIRED':
                    tasks.append({'job':job['name'],'fingerprint':key,'source_files':job['dependencies'],'reason':e.message,'required_entry':'run(ctx)','steps':[s['name'] for s in job['steps']]})
        stage('GENERATE',f'{result["metrics"]["jobs_generated"]} job files available; {len(result["issues"])} unresolved exceptions. No repair loop is run.')
        request={'schema_version':1,'process':cfg['process'],'config':str(config_path.resolve()),'repository':str(paths['repo']),
          'artifact_store':str(paths['agents']),'config_sha256':digest(config_path.read_bytes()),'tools_fingerprint':toolhash,'source_hashes':discovered['sources'],
          'approved_knowledge':answers,'process_flow':result['process_flow'],'tasks':tasks,'rules':['Preserve source behavior.','Never edit source/baselines/comparison rules.','After validation, do not repair generated code.','Do not put business input records in the AI prompt.']}
        write_json(folder/'agent_request.json',request)
        if discovered['issues'] or result['issues'] or discover_only:
            result['status']='DISCOVERED' if discover_only and not result['issues'] else 'BLOCKED'
            result['meaning']='The process is not validated. Safe discovery/generation work was retained; unresolved evidence is listed below.'
        else:
            before.update(snapshot(list((folder/'code').glob('*'))+list((folder/'ddl').glob('*'))))
            write_json(folder/'protected_hashes.json',before)
            stage('EXECUTE','Running every scenario in a new local database and separate output folder.')
            observed=set();mapped=set()
            for item in result['jobs']:
                trace=read_json(folder/item['artifact'].replace('.py','.trace.json'))
                mapped.update(s['id'] for s in trace.get('statements',[]))
            for case in cfg['cases']:
                case_root=_path(paths['base'],case['path']);work=folder/'cases'/case['name'];work.mkdir(parents=True)
                with closing(sqlite3.connect(work/'local.sqlite')) as conn:
                    conn.executescript(local_sql)
                    if case.get('initial_database'):conn.executescript(inside(case_root,case['initial_database']).read_text(encoding='utf-8-sig'))
                outcome={'name':case['name'],'status':'FAILED','comparisons':[],'steps':[],'detail':''}
                result['cases'].append(outcome)
                payload={'case_root':str(case_root),'work_root':str(work),'datasets':cfg['datasets'],'schema':schema,'collation':cfg.get('collation','cp037'),'max_sort_records':cfg.get('max_sort_records',100000)}
                write_json(work/'context.json',payload)
                execution_ok=True
                for job in jobs:
                    step_result=work/(job['name']+'.result.json')
                    command=[sys.executable]+([] if cfg.get('use_site_packages',False) else ['-S'])+['-m','migration.worker',str(work/'context.json'),str(folder/'code'/f'{job["name"]}.py'),str(step_result)]
                    env=os.environ.copy();env['PYTHONPATH']=str(ROOT);env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
                    try:
                        completed=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=int(cfg.get('timeout_seconds',60)))
                        atomic_write(work/(job['name']+'.log'),completed.stdout+completed.stderr)
                        evidence=read_json(step_result) if step_result.exists() else {'status':'FAILED','error':'Worker produced no result.'}
                        observed.update(evidence.get('events',{}))
                        target_rc = evidence.get('return_code')
                        expected_rc = case.get('return_codes',{}).get(job['name'],0)
                        outcome['steps'].append({'job':job['name'],'status':evidence['status'],'exit_code':completed.returncode,'return_code':target_rc,'expected_return_code':expected_rc})
                        outcome['comparisons'].append({'kind':'return_code','name':job['name'],'status':'PASSED' if target_rc==expected_rc and evidence['status']=='PASSED' else 'FAILED','detail':f'Actual return code {target_rc}; expected {expected_rc}.'})
                        if completed.returncode!=0 or evidence['status']!='PASSED':
                            execution_ok=False;outcome['detail']=job['name']+': '+evidence.get('error','Execution failed.');break
                        if target_rc != expected_rc:
                            execution_ok=False;outcome['detail']=f'{job["name"]}: return code {target_rc} differs from expected {expected_rc}.';break
                    except subprocess.TimeoutExpired:
                        execution_ok=False;outcome['detail']=job['name']+': execution exceeded its time limit; no repair or retry was attempted.';break
                for name,relative in case['expected_files'].items():
                    actual=inside(work,cfg['datasets'][name]['path']);expected=inside(case_root,relative)
                    outcome['comparisons'].append(_compare_file(actual,expected,name))
                if case.get('expected_database'):
                    outcome['comparisons']+=_compare_db(work/'local.sqlite',inside(case_root,case['expected_database']))
                elif schema:execution_ok=False;outcome['detail']+=' Database tables exist but no expected database snapshot was supplied.'
                fc=[x for x in outcome['comparisons'] if x['kind']=='file'];dc=[x for x in outcome['comparisons'] if x['kind']=='database']
                outcome.update(file_total=len(fc),file_passed=sum(x['status']=='PASSED' for x in fc),database_total=len(dc),database_passed=sum(x['status']=='PASSED' for x in dc))
                if execution_ok and all(x['status']=='PASSED' for x in outcome['comparisons']):
                    outcome['status']='PASSED';outcome['detail']='All specified outputs and table rows match.';result['metrics']['cases_passed']+=1
                else:
                    result['issues'].append(Blocked(f'Scenario {case["name"]} did not reproduce its baseline. {outcome["detail"]} Review the execution/comparison evidence; generated code and expected results were not repaired.','MIGRATION_MISMATCH',case['name']).issue())
                print(f'  {case["name"]}: {outcome["status"]}',flush=True)
            result['metrics'].update(statements_mapped=len(mapped),statements_observed=len(mapped&observed))
            result['status']=('SYNTHETIC_TESTS_PASSED' if cfg['baseline']['kind']=='synthetic' else 'BASELINE_SCENARIOS_MATCHED') if not result['issues'] else 'VALIDATION_FAILED'
            result['meaning']='All supplied synthetic scenarios matched. This validates the packaged offline workflow for this sample, not a bank application or mainframe runtime.' if result['status']=='SYNTHETIC_TESTS_PASSED' else ('The supplied mainframe baseline scenarios matched; untested scenarios and release approval remain separate.' if result['status']=='BASELINE_SCENARIOS_MATCHED' else 'At least one scenario failed. No automatic repair was attempted.')
        stage('REVIEW','Checking source/baseline integrity and reporting coverage and unresolved scope.')
        mutations=changed(before)
        if mutations:
            result['status']='INTEGRITY_FAILED';result['issues'].append(Blocked('Protected files changed during execution: '+', '.join(mutations)+'. No automatic restoration was attempted.','SOURCE_INTEGRITY').issue())
        result['review']=[{'check':'Source, inventory, expected outputs, and framework bytes unchanged during run','outcome':'FAILED' if mutations else 'PASSED'},
          {'check':'Automatic repair or baseline adjustment','outcome':'Not performed'},
          {'check':'Source-to-target statement map','outcome':f'{result["metrics"].get("statements_mapped",0)} mapped; unobserved statements remain untested'},
          {'check':'Independent mainframe execution','outcome':'Not performed by this package; see baseline provenance'},
          {'check':'Human/independent semantic approval','outcome':'Not granted by automation'}]
    except Exception as exc:
        e=exc if isinstance(exc,Blocked) else Blocked(f'{type(exc).__name__}: {exc}. Execution stopped; no code repair was attempted.','FRAMEWORK_ERROR')
        result['issues'].append(e.issue());result['status']='BLOCKED'
        result['meaning']='A required environment/evidence/execution condition failed. Completed artifacts remain available, but validation was not awarded.'
    finally:
        if before:
            mutations=changed(before)
            if mutations and result['status']!='INTEGRITY_FAILED':
                result['status']='INTEGRITY_FAILED';result['issues'].append(Blocked('Protected files changed during the run: '+', '.join(mutations),'SOURCE_INTEGRITY').issue())
        result['issues']=list({q['id']:q for q in result['issues']}.values())
        write_json(folder/'result.json',result);write_report(folder,result)
        write_json(paths['output']/cfg['process']/'latest.json',{'run':str(folder),'report':str(folder/'modernization_report.html'),'status':result['status']})
        if owned:lock.unlink(missing_ok=True)
    result['report']=str(folder/'modernization_report.html');result['run_folder']=str(folder)
    print('REPORT: '+result['report'],flush=True)
    return result

def register(request_path: Path,job: str,candidate: Path,trace_path: Path) -> Path:
    """Seal a new agent-generated job once; never overwrite a validated/failed attempt."""
    request=read_json(request_path)
    task=next((t for t in request['tasks'] if t['job']==job),None)
    if task is None:raise Blocked('This job has no outstanding generation request.','AGENT_ARTIFACT')
    if request['tools_fingerprint']!=tool_fingerprint():raise Blocked('Framework instructions/tools changed; create a fresh request.','STALE_REQUEST')
    if digest(Path(request['config']).read_bytes())!=request.get('config_sha256'):
        raise Blocked('Process configuration changed after the request; discover again.','STALE_REQUEST')
    repo=Path(request['repository'])
    for relative,expected in request['source_hashes'].items():
        path=inside(repo,relative)
        if not path.is_file() or digest(path.read_bytes())!=expected:raise Blocked('Source changed after the generation request; discover again.','STALE_REQUEST',relative)
    code=candidate.read_text(encoding='utf-8');inspect_python(code,candidate.name)
    trace=read_json(trace_path)
    if trace.get('job')!=job or trace.get('unresolved')!=[] or not trace.get('source_coverage'):
        raise Blocked('Agent trace must name the job, map source_coverage, and have an empty unresolved list.','AGENT_ARTIFACT')
    covered={x['source'] for x in trace['source_coverage']}
    if not set(task['source_files'])<=covered:raise Blocked('Agent trace omits a discovered source dependency.','AGENT_ARTIFACT')
    for row in trace['source_coverage']:
        if row['source'] not in request['source_hashes']:raise Blocked('Trace cites a source outside the request.','AGENT_ARTIFACT')
        line_count=len(inside(repo,row['source']).read_text(encoding='utf-8-sig').splitlines())
        if not isinstance(row.get('start_line'),int) or not isinstance(row.get('end_line'),int) or not 1<=row['start_line']<=row['end_line']<=line_count:
            raise Blocked('Trace ranges need positive start_line/end_line values.','AGENT_ARTIFACT')
    trace['mode']='agent-authored; source coverage is a claim to be reviewed, not proof';trace.setdefault('statements',[])
    target=Path(request['artifact_store'])/task['fingerprint']
    if target.exists():
        prior,_=_load_sealed(target,task['fingerprint'])
        if prior!=code:raise Blocked('A sealed attempt already exists. Automatic replacement/repair is prohibited. A separately authorized generation version is required.','IMMUTABLE_ARTIFACT')
        return target
    _seal_cache(target,code,trace,task['fingerprint']);return target
