"""Reproduce the nine-target acceptance exercise without changing target.json.

The matrix is a test utility. Normal process operation reads one central target
file. Test-specific copies make every target selection and its evidence explicit.
"""
from pathlib import Path
import json,shutil,platform,sys,sqlite3
from migration.common import read_json,write_json,digest,snapshot,changed,Blocked
from .config import load_target
from .controller import run,check_artifact
ROOT=Path(__file__).resolve().parents[2]

def exercise(destination: Path,verify=True):
    """Generate all pairs, compare available runtimes, then switch back to test reuse."""
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    shutil.copytree(ROOT/'sample',destination/'sample')
    config=destination/'sample/process.json';cfg=read_json(config)
    cfg['knowledge']=str(ROOT/'knowledge/answers.json');write_json(config,cfg)
    profile=load_target(ROOT/'target.json');selected=destination/'target.json'
    before=snapshot([p for p in (destination/'sample').rglob('*') if p.is_file()])
    rows=[];full_results=[]
    for language in ('python','java','dotnet'):
        for database in ('sqlite','oracle','bigquery'):
            profile.update(language=language,database=database);write_json(selected,profile)
            print('TARGET MATRIX:',language,database,flush=True)
            result=run(config,selected,verify=verify)
            if result.get('artifact_folder'):check_artifact(Path(result['artifact_folder']))
            v=result['verification'];row={'target':language+'-'+database,'status':result['status'],
                  'generation':v['generation'],'compilation':v['compilation'],'native_database':v['native_database'],
                  'contract_execution':v['contract_execution'],'models_reused':result['metrics']['models_reused'],
                  'job_files_created':result['metrics']['job_files_created'],'job_files_reused':result['metrics']['job_files_reused'],
                  'artifact_folder':result.get('artifact_folder'),
                  'files_passed':sum(c['file_passed'] for c in v.get('cases',[])),
                  'file_checks':sum(c['file_total'] for c in v.get('cases',[])),
                  'database_or_trace_passed':sum(c['database_passed'] for c in v.get('cases',[])),
                  'return_codes_passed':sum(c['rc_passed'] for c in v.get('cases',[]))}
            rows.append(row);full_results.append(result)
            write_json(destination/'matrix-progress.json',rows)
    profile.update(language='python',database='sqlite');write_json(selected,profile)
    repeat=run(config,selected,verify=verify)
    changed_files=changed(before)
    assertions={'nine_targets_generated':all(r['generation']=='PASSED' for r in rows),
       'no_executed_target_test_failed':all(r['status'] not in {'BLOCKED','VALIDATION_FAILED'} for r in rows),
       'source_and_baseline_unchanged':not changed_files,
       'switch_back_reuses_original_artifact':repeat.get('artifact_id')==full_results[0].get('artifact_id') and repeat['metrics'].get('target_artifact_reused',False),
       'switch_back_reuses_five_jobs':repeat['metrics']['job_files_reused']==5}
    receipt={'schema_version':2,'environment':{'os':platform.platform(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version},
             'status':'CHECKS_PASSED_WITH_EXPLICIT_RUNTIME_GAPS' if all(assertions.values()) else 'CHECK_FAILED',
             'assertions':assertions,'targets':rows,'switch_back':repeat,'results':full_results,
             'limits':['No live Oracle/BigQuery execution.','Missing SDKs/drivers are NOT_RUN, not passed.','Synthetic expectations are not mainframe outputs.','No live Copilot or Devin session is performed.']}
    write_json(destination/'matrix_receipt.json',receipt)
    return receipt
