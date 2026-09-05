#!/usr/bin/env python3
"""Verify an extracted v2 release, its regression suites and all target selections.

Run before modifying target.json. This command never deletes previous work, calls
an AI service, installs a dependency, repairs a candidate, or contacts a remote DB.
Runtime gaps remain explicit in the receipt rather than becoming passed tests.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def verify_hashes():
    """Check each shipped byte against the release manifest; this is not a signature."""
    manifest=json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'));bad=[]
    for name,expected in manifest['files'].items():
        p=ROOT/name
        if not p.resolve().is_relative_to(ROOT) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(name)
    if bad:raise RuntimeError('Shipped bytes differ: '+', '.join(bad)+'. Verify a fresh extraction before editing configuration.')
    return {'files_checked':len(manifest['files']),'status':'PASSED'}

def command(name,arguments,folder):
    """Use only the extracted source and retain every command's real exit status."""
    env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
    argv=[sys.executable,'-S',str(ROOT/'modernize.py'),*map(str,arguments)]
    print('RUNNING:',name,flush=True)
    p=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1800)
    text=p.stdout+p.stderr;(folder/(name+'.txt')).write_text(text,encoding='utf-8')
    print(name+': exit '+str(p.returncode),flush=True)
    if p.returncode!=0:raise RuntimeError(name+' failed; read '+str(folder/(name+'.txt')))
    return text

def main():
    """Publish a measured receipt with a fresh-generation check and separate gaps."""
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--require-fresh',action='store_true');args=ap.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder=ROOT/'evidence/package-check'/stamp;folder.mkdir(parents=True,exist_ok=False)
    proof={'schema_version':2,'root':str(ROOT),'status':'FAILED','timestamp_utc':datetime.now(timezone.utc).isoformat(),
           'python':platform.python_version(),'environment':platform.platform(),'actual_windows_test':platform.system()=='Windows',
           'live_agent_session':False,'actual_ibm_execution':False,'live_oracle_bigquery':False}
    try:
        proof['manifest_before']=verify_hashes()
        if args.require_fresh and any((ROOT/n).exists() for n in ('output','.migration/cache','agent_artifacts')):raise RuntimeError('Fresh extraction requires no active output/cache/agent artifacts. Nothing is deleted automatically.')
        command('environment',['doctor'],folder)
        tests=command('tests',['self-test'],folder);count=re.search(r'Ran (\d+) tests',tests)
        if not count:raise RuntimeError('Actual test count was not reported.')
        proof['tests_run']=int(count.group(1))
        skipped=re.search(r'OK \(skipped=(\d+)\)',tests)
        proof['tests_skipped']=int(skipped.group(1)) if skipped else 0
        proof['tests_passed']=proof['tests_run']-proof['tests_skipped']
        command('target_matrix',['verify-targets','--output',folder/'matrix'],folder)
        matrix=json.loads((folder/'matrix/matrix_receipt.json').read_text(encoding='utf-8'))
        proof['matrix_assertions']=matrix['assertions'];proof['targets']=matrix['targets'];proof['switch_back']=matrix['switch_back']['metrics']
        first=matrix['results'][0]['metrics'];proof['first_generation']=first
        if args.require_fresh and (first['models_created']!=5 or first['job_files_created']!=5 or first['job_files_reused']!=0):raise RuntimeError('Fresh sample did not create five new models/job files.')
        if not all(matrix['assertions'].values()):raise RuntimeError('A target-matrix assertion failed.')
        proof['manifest_after']=verify_hashes();proof['status']='CHECKS_PASSED_WITH_EXPLICIT_RUNTIME_GAPS'
        proof['meaning']='Shipped-byte integrity, regressions, nine-target generation and available execution checks passed. NOT_RUN/NOT_AVAILABLE fields are not validation passes.'
    except Exception as exc:proof['error']=type(exc).__name__+': '+str(exc)
    (folder/'verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('VERIFICATION:',proof['status']);print('EVIDENCE:',folder/'verification.json')
    return 0 if proof['status']=='CHECKS_PASSED_WITH_EXPLICIT_RUNTIME_GAPS' else 1
if __name__=='__main__':raise SystemExit(main())
