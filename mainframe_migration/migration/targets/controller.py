"""One target-aware run: discover, reuse, emit, verify, and publish one report.

The source behavior model, language code, database components, and test evidence
have separate identities. A SQLite pass can never become an Oracle/BigQuery pass
by copying a status flag. Existing sealed artifacts are never edited in place.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import copy,html,json,os,platform,re,shutil,sys,uuid
from migration.common import Blocked,atomic_write,digest,fingerprint,inside,read_json,write_json,snapshot,changed
from migration.discovery import discover
from migration.inventory import read_inventory
from migration.process_flow import normalize_flow
from migration.runner import load_config,knowledge,_baseline_files,_check_baseline,_path
from .config import load_target,target_identity
from .model import obtain,behavior_key
from .schema import parse_schema,capabilities
from .emit import emit_job
from .package import assemble,EXT,TEMPLATES

ROOT=Path(__file__).resolve().parents[2]
VERSION='2.0.0'

def file_hashes(folder: Path,exclude=()) -> dict:
    """Hash the exact file set; extra files are not silently accepted in sealed artifacts."""
    return {p.relative_to(folder).as_posix():digest(p.read_bytes()) for p in sorted(folder.rglob('*')) if p.is_file() and p.relative_to(folder).as_posix() not in exclude}

def check_artifact(folder: Path) -> dict:
    """Verify the complete sealed generation, including target metadata and all adapters."""
    seal=read_json(folder/'artifact-manifest.json')
    actual=file_hashes(folder,{'artifact-manifest.json'})
    if actual!=seal.get('files'):raise Blocked('Generated artifacts changed or files were added/removed. No repair or replacement is performed.','ARTIFACT_INTEGRITY',str(folder))
    return seal

def _language_code(store,key,model,language):
    """Reuse only code with the same source model, language, and emitter implementation."""
    folder=store/'code'/key
    if folder.exists():
        seal=read_json(folder/'seal.json');text=(folder/'job.txt').read_text(encoding='utf-8')
        if seal!={'key':key,'sha256':digest(text.encode())}:raise Blocked('Language-code cache changed; it is not silently regenerated.','CODE_CACHE_INTEGRITY',str(folder))
        return text,True
    text=emit_job(model,language);folder.mkdir(parents=True,exist_ok=False)
    atomic_write(folder/'job.txt',text);write_json(folder/'seal.json',{'key':key,'sha256':digest(text.encode())})
    return text,False

def _schema(cfg,paths,discovery):
    """Read authoritative DDL rather than treating the SQLite table layout as the specification."""
    names=list(cfg.get('ddl_sources',[]));result={}
    if not names:
        needed={e['to'] for e in discovery['edges'] if e['kind']=='SQL_TABLE_CANDIDATE'}
        for members in discovery['index'].values():
            for p in members:
                if p.suffix.lower() not in {'.sql','.ddl'}:continue
                tables={m.upper() for m in re.findall(r'CREATE\s+TABLE\s+([A-Z][A-Z0-9_]*)',p.read_text(encoding='utf-8-sig'),re.I)}
                if tables&needed:names.append(p.relative_to(paths['repo']).as_posix())
    for name in dict.fromkeys(names):
        p=inside(paths['repo'],name)
        if not p.is_file():raise Blocked('Authoritative DDL is missing: '+name,'MISSING_DDL')
        part=parse_schema(p.read_text(encoding='utf-8-sig'))
        if set(part)&set(result):raise Blocked('Duplicate source table definitions.','DDL')
        result.update(part);discovery['sources'][name]=digest(p.read_bytes())
    for e in discovery['edges']:
        if e['kind']=='SQL_TABLE_CANDIDATE' and e['to'] not in result:
            discovery['issues'].append(Blocked('Provide the authoritative schema for '+e['to']+'. SQLite column guesses will not be used.','MISSING_DDL',e['from']).issue())
    return result

def _legacy_runs(process_root):
    """Recognize prior v1 deliveries without pretending they contain a portable model."""
    found=[]
    if not process_root.exists():return found
    for result_path in process_root.glob('*/result.json'):
        try:
            result=read_json(result_path)
            if 'target' in result:continue
            for p in (result_path.parent/'code').glob('*.py'):
                found.append({'job':p.stem,'language':'python','database':'sqlite','sha256':digest(p.read_bytes()),
                    'path':str(p),'prior_status':result.get('status','unknown'),'reuse_status':'RECORDED_LEGACY; requires source-linked v2 model, not reverse translation from SQLite'})
        except (OSError,ValueError):continue
    return found

def write_report(folder,result):
    """Keep progress, retargeting decisions, evidence, and open questions in one readable page."""
    def esc(x):return html.escape(str(x))
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    target=result.get('target',{});metrics=result.get('metrics',{})
    body='<h1>Modernization & retargeting report</h1><p class="strap">'+esc(result.get('process','Unknown process'))+' · '+esc(target.get('language','?'))+' / '+esc(target.get('database','?'))+'</p>'
    body+='<h2>'+esc(result['status'])+'</h2><p>'+esc(result.get('summary',''))+'</p>'
    flow=result.get('process_flow')
    if flow:
        body+='<h2>Documented process flow</h2><p>'+esc(flow['authority'])+'</p>'
        body+='<p>Input: '+esc(flow['inventory']['path'])+'. Configured job order: '+esc(', '.join(flow['execution_order']))+'. Evidence: '+esc(flow['order_evidence'] or 'UNRESOLVED')+'</p>'
        body+=table(['Job / step','Program / kind','Section / description','Documented input','Documented output','Source location'],[
            (r['job']+' / '+r['step'],r['program']+' / '+r['kind'],r['section']+' / '+r['description']+
             (' / '+ '; '.join(str(k)+': '+str(v) for k,v in r['extra_fields'].items()) if r.get('extra_fields') else ''),
             '; '.join(r['inputs']) or ('NONE' if 'input' in r['fields_present'] else 'Not documented'),
             '; '.join(r['outputs']) or ('NONE' if 'output' in r['fields_present'] else 'Not documented'),
             str(r['source'])+':'+str(r['row'])) for r in flow['rows']])
        body+='<h2>Dataset destinations</h2><p>Paths are the configured paths used inside each isolated test run. UNRESOLVED requires an explicit binding. Configured role is a process lifecycle role, not an inferred DD direction.</p>'
        body+=table(['Dataset','Configured role','Configured path','Destination status','Documented outputs at'],[
            (d['dataset'],d['configured_role'] or 'UNRESOLVED',d['path'] or 'UNRESOLVED',d['destination_status'],
             ', '.join(r['job']+'/'+r['step'] for r in d['documented_outputs']) or 'Not documented') for d in flow['dataset_bindings']])
        if flow['database_objects']:
            body+='<h2>Documented database objects</h2>'+table(['Table','Source definition','Selected database'],[
                (obj['name'],obj['schema_status'],target.get('database','UNRESOLVED')) for obj in flow['database_objects']])
    body+='<h2>What was reused and what changed</h2>'+table(['Measure','Observed'],metrics.items())
    body+='<p>Previous target: '+esc(result.get('previous_target','none'))+'. '+esc(result.get('retarget_reason',''))+'</p>'
    body+='<h2>Generated jobs</h2>'+table(['Job','Source model','Language code','Model fingerprint'],[(j['job'],j['model_status'],j['code_status'],j['model_key'][:16]) for j in result.get('jobs',[])])
    v=result.get('verification',{})
    body+='<h2>Verification—not all checks mean the same thing</h2>'+table(['Evidence','Status'],[(k,v.get(k,'NOT_RUN')) for k in ['generation','compilation','native_database','contract_execution','baseline_kind']])
    body+='<p>'+esc(v.get('detail',''))+'</p>'
    coverage=v.get('statement_evidence',{})
    if coverage:body+='<p>Mapped source statements exercised: '+esc(coverage.get('exercised',0))+' / '+esc(coverage.get('mapped',0))+'. This is not complete path coverage.</p>'
    cases=v.get('cases',[])
    body+=table(['Scenario','Mode','Files','Database / operation checks','Return codes','Outcome'],[(c['name'],c['mode'],str(c.get('file_passed',0))+'/'+str(c.get('file_total',0)),str(c.get('database_passed',0))+'/'+str(c.get('database_total',0)),str(c.get('rc_passed',0))+'/'+str(c.get('rc_total',0)),c['status']) for c in cases])
    body+='<h2>Questions and blockers</h2>'+table(['Owner','Code','Question / finding'],[(x.get('owner','Migration engineer'),x.get('code',''),x.get('question',x.get('message',''))) for x in result.get('issues',[])])
    body+='<h2>Stages</h2>'+table(['Stage','What happened'],[(s['stage'],s['detail']) for s in result.get('stages',[])])
    body+='<h2>Artifacts and evidence</h2>'+table(['Location','Value'],[(k,result.get(k,'')) for k in ('artifact_folder','artifact_id','run_folder','process_flow_file','registry_file','environment')])
    body+='<h2>Boundaries</h2><p>'+esc('This is a bounded source workbench, not a universal COBOL/JCL compiler. Synthetic expectations are not IBM mainframe outputs. Contract recordings are not live Oracle, BigQuery, or native-driver tests. A generated or compiled target is not production validated. No application rule was repaired. This review was performed in this assistant session, not by an independent third-party reviewer.')+'</p>'
    page='<!doctype html><html><head><meta charset="utf-8"><title>Modernization report</title><style>body{font:16px/1.5 Segoe UI,Arial,sans-serif;color:#182b3a;max-width:1200px;margin:32px auto;padding:0 24px}h1{font-size:34px}h2{margin-top:32px;color:#164f67}.strap{font-size:20px;color:#586b76}table{width:100%;border-collapse:collapse;margin:16px 0;table-layout:fixed}th,td{text-align:left;padding:10px;vertical-align:top;border-bottom:1px solid #d9e4e9;overflow-wrap:anywhere}th{background:#eaf2f5}p{max-width:1050px}</style></head><body>'+body+'</body></html>'
    atomic_write(folder/'modernization_report.html',page);write_json(folder/'result.json',result)

def run(config_path: Path,target_path: Path|None=None,output_override: Path|None=None,verify: bool=True,contract_only: bool=False,discover_only: bool=False):
    """Perform all locally available stages once; missing capabilities remain visible."""
    config_path=Path(config_path).resolve();result={'process':config_path.stem,'status':'BLOCKED','target':{},'jobs':[],'issues':[],'stages':[],
        'metrics':{'jobs_discovered':0,'models_created':0,'models_reused':0,'job_files_created':0,'job_files_reused':0},
        'verification':{'generation':'NOT_RUN','compilation':'NOT_RUN','native_database':'NOT_RUN','contract_execution':'NOT_RUN'},
        'environment':platform.platform()+' / Python '+platform.python_version()}
    folder=ROOT/'output'/'configuration-errors'/uuid.uuid4().hex;lock=None;before={};owned=False
    def stage(name,text):
        print('['+name+'] '+text,flush=True);result['stages'].append({'stage':name,'detail':text});write_report(folder,result)
    try:
        cfg,paths=load_config(config_path)
        paths['configuration']=config_path
        if {'target','language','database','target_database','target_language'}&set(cfg):raise Blocked('Put target choices only in target.json, not in the process configuration.','TARGET_CONFIG')
        if output_override is not None:paths['output']=Path(output_override).resolve()
        target_path=Path(target_path).resolve() if target_path is not None else (_path(paths['base'],cfg['target_file']) if cfg.get('target_file') else ROOT/'target.json')
        target=load_target(target_path);result['target']=target;result['process']=cfg['process'];pair=target_identity(target)
        process_root=paths['output']/cfg['process'];folder=process_root/'runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir(parents=True,exist_ok=False)
        result['run_folder']=str(folder);store=paths['cache']/'retarget-v2';store.mkdir(parents=True,exist_ok=True)
        lock=store/'.run-lock'
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            with os.fdopen(fd,'w') as f:f.write(json.dumps({'pid':os.getpid(),'run':str(folder)}))
            owned=True
        except FileExistsError:raise Blocked('Another retargeting run holds the shared-store lock. Verify the recorded PID before removing a stale lock.','RUN_LOCK',str(lock))
        registry_file=process_root/'target_registry.json';result['registry_file']=str(registry_file)
        registry=read_json(registry_file) if registry_file.exists() else {'schema_version':2,'history':[],'legacy_deliveries':_legacy_runs(process_root)}
        if registry.get('history'):
            checksum=registry_file.with_suffix('.sha256')
            if not checksum.exists() or checksum.read_text().strip()!=digest(registry_file.read_bytes()):raise Blocked('Target history changed without its recorded checksum.','REGISTRY_INTEGRITY')
        previous=registry['history'][-1]['target'] if registry['history'] else None;result['previous_target']=target_identity(previous) if previous else 'none'
        if previous and previous['language']==target['language'] and previous['database']!=target['database']:result['retarget_reason']='Database changed: reuse eligible behavior/language artifacts; replace database components and invalidate database validation.'
        elif previous and previous['language']!=target['language']:result['retarget_reason']='Language changed: reuse eligible behavior models; generate native language artifacts and require new runtime validation.'
        elif previous:result['retarget_reason']='Target is unchanged: reuse only intact fingerprint matches and rerun available validation.'
        else:result['retarget_reason']='First source-linked v2 generation. Historical v1 deliveries, when present, are recorded separately.'
        stage('DISCOVER','Reading the process document, JCL sources, and authoritative definitions; existing targets are not modified.')
        rows=read_inventory(paths['inventory'],cfg.get('sheet','Process'))
        result['process_flow_file']=str(folder/'process_flow.json')
        result['process_flow']=normalize_flow(rows,cfg,paths['inventory'])
        write_json(folder/'process_flow.json',result['process_flow'])
        found=discover(paths['repo'],rows,cfg)
        result['process_flow']=normalize_flow(rows,cfg,paths['inventory'],found)
        found['process_flow']=result['process_flow']
        write_json(folder/'process_flow.json',result['process_flow'])
        result['issues']+=found['issues'];result['metrics']['jobs_discovered']=len(set(r['job'] for r in rows))
        if set(cfg['execution_order'])!=set(r['job'] for r in rows):raise Blocked('Execution order must name every inventory job exactly once.','PROCESS_ORDER')
        if not cfg.get('order_evidence'):result['issues'].append(Blocked('Provide evidence for cross-job execution order; document row order is not a scheduler rule.','PROCESS_ORDER').issue())
        for binding in result['process_flow']['dataset_bindings']:
            if binding['destination_status']=='UNRESOLVED' and (binding['documented_inputs'] or binding['documented_outputs']):
                result['issues'].append(Blocked('Documented dataset has no configured destination: '+binding['dataset']+'. Supply its explicit dataset binding.','DATASET_BINDING').issue())
        models=[];codes={};issue_count=len(found['issues']);schema=_schema(cfg,paths,found);result['issues']+=found['issues'][issue_count:];answers,_=knowledge(paths['knowledge'],cfg['process'])
        found['schema']=schema
        result['process_flow']=normalize_flow(rows,cfg,paths['inventory'],found)
        found['process_flow']=result['process_flow']
        write_json(folder/'process_flow.json',result['process_flow'])
        for obj in result['process_flow']['database_objects']:
            if obj['schema_status']=='UNRESOLVED':
                result['issues'].append(Blocked('Documented table has no authoritative DDL: '+obj['name']+'. Supply its source definition.','MISSING_DDL').issue())
        for job in found['jobs']:
            for s in job['steps']:
                for dd in s['dds'].values():
                    if 'dsn' in dd and dd['dsn'] not in cfg['datasets']:result['issues'].append(Blocked('Dataset binding is missing: '+dd['dsn'],'DATASET_BINDING',job['source']).issue(job['name']))
        write_json(folder/'discovery.json',{k:v for k,v in found.items() if k!='index'})
        protected=[paths['repo']/p for p in found['sources']]+_baseline_files(cfg,paths)+[config_path,target_path,paths['inventory'],paths['knowledge']]+[p for p in (ROOT/'migration').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        if cfg['baseline'].get('manifest'):protected.append(_path(paths['base'],cfg['baseline']['manifest']))
        before=snapshot(protected)
        result['metrics']['source_members']=len(found['sources'])
        if discover_only:
            result['status']='DISCOVERED_WITH_GAPS' if result['issues'] else 'DISCOVERED';return result
        # Generation never fabricates missing baselines; available evidence is verified first.
        baseline_ok=True
        try:_check_baseline(cfg,paths)
        except Blocked as exc:
            baseline_ok=False;result['issues'].append(exc.issue())
            if exc.code=='BASELINE_INTEGRITY':raise
        if cfg.get('generation_mode','agent')=='agent':
            from .agent import request_body,load_registered
            found['process_issues']=list(result['issues'])
            request=request_body(cfg,paths,target,target_path,found,schema,answers,registry)
            write_json(folder/'agent_request.json',request)
            registered=load_registered(request)
            if registered is None:
                raise Blocked('The coding agent must generate/register this target using agent_request.json. The local runner does not call a hidden AI service or silently use the synthetic compiler.','AGENT_REQUIRED')
            files,payload,review=registered
            if any(q['code'] not in {'TEST_EVIDENCE'} for q in result['issues']):raise Blocked('Source/execution gaps remain; registration is not a waiver.','SOURCE_GAPS')
            stage('GENERATE','Loading the sealed agent target. Review declarations are not independent proof; executable checks follow.')
            result['agent_review']={'method':review['method'],'reviewer':review['reviewer'],'status':'DECLARED_SOURCE_TRACE; not a proof of equivalence'}
            models=payload['models']
            for job in found['jobs']:
                key=behavior_key(job,found['sources'],cfg,answers)
                result['jobs'].append({'job':job['name'],'model_key':key,'code_key':fingerprint(files['jobs/'+job['name']+EXT[target['language']]]),'model_status':'AGENT_SOURCE_TRACE','code_status':'REGISTERED_UNCHANGED'})
            result['metrics']['registered_job_files']=len(result['jobs'])
        else:
            stage('MODEL','Loading or creating sealed source behavior models. Database selection is not part of their identity.')
            emitter=digest((Path(__file__).parent/'emit.py').read_bytes())
            for job in sorted(found['jobs'],key=lambda j:cfg['execution_order'].index(j['name'])):
                if any(q.get('job')==job['name'] for q in result['issues']):continue
                try:
                    key=behavior_key(job,found['sources'],cfg,answers);m,reused=obtain(store,key,job,found['index'],cfg)
                    result['metrics']['models_reused' if reused else 'models_created']+=1
                    code_key=fingerprint({'model':key,'language':target['language'],'emitter':emitter})
                    code,code_reused=_language_code(store,code_key,m,target['language'])
                    result['metrics']['job_files_reused' if code_reused else 'job_files_created']+=1
                    result['jobs'].append({'job':job['name'],'model_key':key,'code_key':code_key,'model_status':'REUSED' if reused else 'CREATED','code_status':'REUSED' if code_reused else 'CREATED'})
                    models.append(m);codes[m['job']]=code
                except Blocked as exc:result['issues'].append(exc.issue(job['name']))
            if len(models)!=result['metrics']['jobs_discovered']:raise Blocked('Not every scoped job has a complete behavior model. No partial process is marked migrated.','INCOMPLETE_PROCESS')
            if any(q['code'] not in {'TEST_EVIDENCE'} for q in result['issues']):raise Blocked('Source or execution gaps prevent a complete target generation.','SOURCE_GAPS')
            stage('GENERATE','Assembling native job files, selected database adapter, target DDL, dependency declarations, and source lineage.')
            files,payload=assemble(models,schema,cfg,target,job_codes=codes)
        artifact_id=fingerprint({n:digest(t.encode()) for n,t in files.items()})
        artifact=process_root/'targets'/pair/artifact_id;result['artifact_id']=artifact_id;result['artifact_folder']=str(artifact)
        reused_artifact=artifact.exists()
        if reused_artifact:check_artifact(artifact)
        else:
            temporary=artifact.with_name('.building-'+uuid.uuid4().hex);temporary.mkdir(parents=True,exist_ok=False)
            for n,text in files.items():atomic_write(inside(temporary,n),text)
            write_json(temporary/'artifact-manifest.json',{'schema_version':2,'artifact_id':artifact_id,'target':pair,'files':file_hashes(temporary)})
            temporary.rename(artifact)
        result['metrics'].update(target_artifact_reused=reused_artifact,generated_job_files=len(models),steps=sum(len(m['steps']) for m in models))
        result['verification']['generation']='PASSED';result['verification']['baseline_kind']=cfg['baseline']['kind']
        result['issues']+=[{**i,'owner':'Architecture / migration review'} for i in payload['capability_blockers']]
        if verify and target['validation'].get('run_local',True):
            stage('VERIFY','Compiling available runtimes and executing appropriate local checks. Remote databases are not contacted.')
            from .verify import verify_target
            result['verification']=verify_target(artifact,folder/'verification',cfg,paths,payload,target,baseline_ok,contract_only)
        v=result['verification']
        if v.get('failed'):result['status']='VALIDATION_FAILED'
        elif payload['capability_blockers']:result['status']='GENERATED_WITH_CAPABILITY_BLOCKERS'
        elif v.get('native_database')=='PASSED' and v.get('compilation')=='PASSED':result['status']='SYNTHETIC_TARGET_VALIDATED' if cfg['baseline']['kind']=='synthetic' else 'BASELINE_SCENARIOS_MATCHED'
        else:result['status']='GENERATED_NOT_FULLY_VALIDATED'
        result['summary']='Generation, compilation, contract execution and live database validation are separate evidence levels. No old target validation was carried forward.'
        if changed(before):raise Blocked('Protected sources, test evidence, or framework files changed. Validation cannot be recorded as successful.','PROTECTED_FILE_CHANGED')
        registry['history'].append({'run_id':folder.name,'target':target,'artifact_id':artifact_id,'artifact_folder':str(artifact),
            'status':result['status'],'model_keys':{j['job']:j['model_key'] for j in result['jobs']},'verification':result['verification'],
            'baseline_fingerprint':fingerprint(snapshot(_baseline_files(cfg,paths))), 'source_fingerprint':fingerprint(found['sources'])})
        write_json(registry_file,registry);atomic_write(registry_file.with_suffix('.sha256'),digest(registry_file.read_bytes())+'\n')
        stage('REPORT','Saved target history, exact artifact fingerprints, validation results, and remaining capability gaps.')
    except Exception as exc:
        issue=exc.issue() if isinstance(exc,Blocked) else {'code':'FRAMEWORK_ERROR','question':type(exc).__name__+': '+str(exc),'owner':'Migration engineer'}
        if issue not in result['issues']:result['issues'].append(issue)
        result['status']='BLOCKED';result['summary']='The run stopped without repairing source, generated code, or expected results.'
    finally:
        modified=changed(before)
        if modified:result['status']='BLOCKED';result['issues'].append({'code':'PROTECTED_FILE_CHANGED','question':'Protected files changed: '+', '.join(modified),'owner':'Migration engineer'})
        result.setdefault('run_folder',str(folder));write_report(folder,result)
        if owned:
            process_root=paths['output']/cfg['process'];atomic_write(process_root/'modernization_report.html',(folder/'modernization_report.html').read_bytes());write_json(process_root/'latest_result.json',result)
            lock.unlink(missing_ok=True)
    return result
