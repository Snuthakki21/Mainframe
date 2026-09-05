"""Bind a coding agent's native delivery to one source snapshot and one target.

This is the handoff used by Copilot/Devin, not a hidden call to a model service.
Review declarations are evidence provided by the agent/reviewer, not independent
proof of semantic equivalence. The same executable validation then tests it.
"""
from pathlib import Path
import json,shutil,re,ast
from migration.common import Blocked,digest,fingerprint,inside,read_json,write_json,atomic_write,snapshot,changed
from .config import load_target,target_identity
from .package import EXT


def request_body(cfg,paths,target,target_path,discovery,schema,answers,registry):
    """Include every interpretation input; changing language/DB creates a new request."""
    source_files={str((paths['repo']/p).resolve()):v for p,v in discovery['sources'].items()}
    source_id=fingerprint(discovery['sources'])
    reuse=[{'target':h['target'],'artifact_folder':h['artifact_folder'],'artifact_id':h['artifact_id'],
            'instruction':'Eligible reference only. Preserve intact language files when behavior is unchanged; do not inherit validation.'}
           for h in registry.get('history',[]) if h['target']['language']==target['language'] and h.get('source_fingerprint')==source_id]
    body={'schema_version':2,'process':cfg['process'],'target':target,'configuration':cfg,
          'configuration_base':str(paths['base']),'target_path':str(target_path),'source_files':source_files,
          'repository':str(paths['repo']),'jobs':discovery['jobs'],'schema':schema,'answers':answers,
          'reuse_candidates':reuse,'registration_root':str(paths['agents']/'targets-v2'),
          'requirement':'Preserve source behavior. No automatic repair. Generate one native file per job plus a complete selected-target runtime and DDL.'}
    # Previous target history is a hint, not a business-input change.
    key=fingerprint({k:v for k,v in body.items() if k!='reuse_candidates'})
    return {**body,'request_id':key}


def check_request(request):
    """A registration cannot quietly bind code to a different source or target."""
    expected=fingerprint({k:v for k,v in request.items() if k not in {'request_id','reuse_candidates'}})
    if request.get('request_id')!=expected:raise Blocked('The agent request was modified. Run discovery again rather than editing the request.','AGENT_REQUEST_INTEGRITY')
    if changed(request['source_files']):raise Blocked('Source files changed after this agent request. Generate a new request.','AGENT_SOURCE_CHANGED')
    if load_target(Path(request['target_path']))!=request['target']:raise Blocked('Target selection changed after the request. Do not register a stale target.','AGENT_TARGET_CHANGED')


def _hashes(folder):
    return {p.relative_to(folder).as_posix():digest(p.read_bytes()) for p in sorted(folder.rglob('*')) if p.is_file()}


def register(request_path,candidate,review_path):
    """Seal a complete native candidate once. Never patch, overwrite, or auto-approve it."""
    request=read_json(Path(request_path));check_request(request);candidate=Path(candidate).resolve()
    review=read_json(Path(review_path));target=request['target'];language=target['language']
    if review.get('request_id')!=request['request_id'] or not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip():raise Blocked('Review needs this request ID and an identified reviewer.','AGENT_REVIEW')
    if review.get('method') not in {'agent_self_review','separate_agent_review','human_review'}:raise Blocked('Label the review method honestly; do not invent independent review.','AGENT_REVIEW')
    if review.get('unresolved_fidelity_findings')!=[]:raise Blocked('Unresolved fidelity findings prevent registration. No repair is performed.','AGENT_REVIEW')
    job_names={j['name'] for j in request['jobs']}
    if set(review.get('jobs',{}))!=job_names:raise Blocked('Every scoped job needs source-to-target trace evidence.','AGENT_TRACE')
    files={}
    for p in candidate.rglob('*'):
        if p.is_symlink():raise Blocked('Candidate links are not allowed.','AGENT_ARTIFACT')
        if not p.is_file():continue
        name=p.relative_to(candidate).as_posix();inside(candidate,name)
        if '__pycache__' in p.parts or p.suffix.lower() in {'.dll','.exe','.class','.db','.sqlite','.jar'}:raise Blocked('Submit source artifacts, not execution outputs or binaries.','AGENT_ARTIFACT')
        files[name]=p.read_text(encoding='utf-8-sig')
    required={'package.json','target.json','database/schema.sql','database/logical_schema.json','database/capabilities.json','dependencies.json','README.md'}
    required|={'python':{'_entry.py','_runtime.py','_database.py'},'java':{'Main.java','MfRuntime.java','MfDatabase.java','Json.java'},'dotnet':{'Main.cs','MfRuntime.cs','MfDatabase.cs','MigratedProcess.csproj','NuGet.Config'}}[language]
    required|={'jobs/'+j+EXT[language] for j in job_names}
    if required-set(files):raise Blocked('Candidate is missing required files: '+', '.join(sorted(required-set(files))),'AGENT_ARTIFACT')
    actual_jobs={Path(n).stem for n in files if n.startswith('jobs/') and Path(n).suffix==EXT[language]}
    if actual_jobs!=job_names:raise Blocked('Job files must exactly match the scoped inventory.','AGENT_ARTIFACT')
    if json.loads(files['target.json'])!=target:raise Blocked('Candidate target.json differs from the requested target.','AGENT_TARGET_CHANGED')
    payload=json.loads(files['package.json']);declared_schema=json.loads(files['database/logical_schema.json'])
    if payload.get('language')!=language or payload.get('database')!=target['database']:raise Blocked('Candidate language/database declaration does not match.','AGENT_TARGET_CHANGED')
    if payload.get('schema')!=request['schema'] or declared_schema!=request['schema']:raise Blocked('Candidate logical schema differs from source evidence.','AGENT_SCHEMA')
    cfg=request['configuration']
    for key in ('datasets','execution_order'):
        if payload.get(key)!=cfg[key]:raise Blocked('Candidate changed '+key+' from the process contract.','AGENT_CONTRACT')
    from .schema import capabilities,ddl
    blockers=capabilities(request['schema'],target['database'])
    if payload.get('capability_blockers')!=blockers:raise Blocked('Candidate suppressed or changed target capability blockers.','AGENT_CAPABILITY')
    if files['database/schema.sql']!=ddl(request['schema'],target['database']):raise Blocked('Candidate target DDL differs from the supported authoritative schema projection.','AGENT_SCHEMA')
    model_jobs={m.get('job') for m in payload.get('models',[])}
    if model_jobs!=job_names:raise Blocked('Run metadata must account for every job.','AGENT_CONTRACT')
    for job in request['jobs']:
        entry=review['jobs'][job['name']]
        if set(entry.get('source_paths',[]))!=set(job['dependencies']):raise Blocked('Trace must account for every dependency for '+job['name'],'AGENT_TRACE')
        traces=entry.get('trace',[])
        if not traces:raise Blocked('Add concrete source-to-generated locations for '+job['name'],'AGENT_TRACE')
        for row in traces:
            if row.get('source') not in job['dependencies'] or not isinstance(row.get('intent'),str) or not row['intent'].strip():raise Blocked('Trace source or plain-English intent is missing.','AGENT_TRACE')
            if type(row.get('source_line')) is not int or row['source_line']<1:raise Blocked('Trace source line must be positive.','AGENT_TRACE')
            source=inside(Path(request['repository']),row['source'])
            if row['source_line']>len(source.read_text(encoding='utf-8-sig').splitlines()):raise Blocked('Trace points beyond source file.','AGENT_TRACE')
            if row.get('generated_file') not in files or type(row.get('generated_line')) is not int or not 1<=row['generated_line']<=len(files[row['generated_file']].splitlines()):raise Blocked('Trace generated location is not present.','AGENT_TRACE')
        text=files['jobs/'+job['name']+EXT[language]]
        if re.search(r'\bTODO\b|NotImplementedException|NotImplementedError',text):raise Blocked('Unfinished job implementation cannot be registered.','AGENT_ARTIFACT')
        if language=='python':
            tree=ast.parse(text);compile(tree,job['name'],'exec')
            if not ast.get_docstring(tree):raise Blocked('Job needs a plain-English purpose header.','AGENT_DOCUMENTATION')
        elif not text.lstrip().startswith(('/*','//')):raise Blocked('Job needs a plain-English purpose header.','AGENT_DOCUMENTATION')
    location=Path(request['registration_root'])/request['request_id']
    if location.exists():
        saved=load_registered(request)
        if saved[0]!=files:raise Blocked('A candidate is already sealed for this request. It is not overwritten or repaired. A separately authorized attempt needs a new agent_generation_version.','AGENT_ALREADY_SEALED')
        return str(location)
    location.mkdir(parents=True,exist_ok=False)
    for name,text in files.items():atomic_write(inside(location/'candidate',name),text)
    write_json(location/'review.json',review)
    write_json(location/'seal.json',{'request_id':request['request_id'],'candidate_hashes':_hashes(location/'candidate'),'review_sha256':digest((location/'review.json').read_bytes())})
    return str(location)


def load_registered(request):
    """Return only an unchanged registered delivery for the current request."""
    check_request(request);folder=Path(request['registration_root'])/request['request_id']
    if not folder.exists():return None
    seal=read_json(folder/'seal.json')
    if seal.get('request_id')!=request['request_id'] or seal.get('candidate_hashes')!=_hashes(folder/'candidate') or seal.get('review_sha256')!=digest((folder/'review.json').read_bytes()):raise Blocked('Registered agent candidate or review changed. No repair is performed.','AGENT_ARTIFACT_INTEGRITY')
    files={n:(folder/'candidate'/n).read_text(encoding='utf-8') for n in seal['candidate_hashes']}
    return files,json.loads(files['package.json']),read_json(folder/'review.json')
