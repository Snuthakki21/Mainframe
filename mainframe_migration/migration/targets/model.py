"""Create a source-linked, language-neutral behavior model for retargeting.

A model is not reverse-engineered from Python or SQLite. It retains the parsed
source statements and utility operations. Reuse is content-addressed and sealed;
changing a target is not a reason to re-read unchanged source business rules.
"""
from __future__ import annotations
from pathlib import Path
from migration.common import Blocked,read_json,write_json,fingerprint,digest
from migration.compiler import compile_job,program,walk,sort_keys

MODEL_VERSION='portable-behavior-2.0'

def extract(job,index,fmt):
    """Use the existing front end's fail-closed checks, then retain its source tree."""
    _,trace=compile_job(job,index,fmt)
    programs=[program(n,index,fmt) for n in trace['programs']]
    steps=[]
    for step in job['steps']:
        copy=dict(step)
        if step['program'] in {'SORT','ICEMAN'}:copy['sort_keys']=sort_keys(step)
        steps.append(copy)
    return {'model_version':MODEL_VERSION,'job':job['name'],'source':job['source'],
            'dependencies':job['dependencies'],'programs':programs,'steps':steps,'trace':trace}

def behavior_key(job,source_hashes,cfg,answers):
    """Ignore target technology and test records; include facts that change source meaning."""
    from migration import compiler,discovery
    parser_hash={Path(m.__file__).name:digest(Path(m.__file__).read_bytes()) for m in (compiler,discovery)}
    parser_hash['model.py']=digest(Path(__file__).read_bytes())
    return fingerprint({'version':MODEL_VERSION,'job':job,
        'sources':{p:source_hashes[p] for p in job['dependencies']},
        'format':cfg['source_format'],'collation':cfg.get('collation'),
        'approved_answers':answers,'front_end':parser_hash})

def obtain(store: Path,key: str,job,index,cfg) -> tuple[dict,bool]:
    """Load an intact source model or create it once. Never overwrite a corrupt model."""
    location=store/'models'/key
    if location.exists():
        model=read_json(location/'model.json');seal=read_json(location/'seal.json')
        if seal.get('key')!=key or fingerprint(model)!=seal.get('model_sha256'):
            raise Blocked('A stored behavior model changed. It is not repaired or silently regenerated.','MODEL_INTEGRITY',str(location))
        return model,True
    model=extract(job,index,cfg['source_format'])
    location.mkdir(parents=True,exist_ok=False)
    write_json(location/'model.json',model);write_json(location/'seal.json',{'key':key,'model_sha256':fingerprint(model)})
    return model,False

def encoding_tables(cfg: dict) -> dict:
    """Make byte-to-character mappings explicit so all native runtimes use identical bytes."""
    result={}
    for name in {cfg.get('collation','cp037')}|{s['encoding'] for s in cfg['datasets'].values()}:
        if name.lower() in {'ascii','us-ascii'}:
            result[name]=''.join(chr(i) for i in range(128));continue
        try:
            text=bytes(range(256)).decode(name,errors='strict')
            if len(text)!=256 or len(set(text))!=256 or text.encode(name)!=bytes(range(256)):raise ValueError('not a one-to-one single-byte encoding')
        except (LookupError,UnicodeError,ValueError) as exc:
            raise Blocked(f'Encoding {name} needs an explicit portable byte mapping: {exc}','ENCODING_PROFILE') from exc
        result[name]=text
    return result
