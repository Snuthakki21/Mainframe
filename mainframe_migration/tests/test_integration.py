"""End-to-end and deliberately hostile tests use actual generated job processes.

Every test has its own copied synthetic source, cache, inputs, and expected results.
Intentional mutations are fault injections into disposable test copies; the runner
never makes these changes and never repairs a source rule or expected result.
"""
from __future__ import annotations
import contextlib
from contextlib import closing
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from migration.common import Blocked,digest,read_json,write_json
from migration.runner import run,register

ROOT=Path(__file__).resolve().parents[1]

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='migration test with spaces ')
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'sample',self.root/'sample')
        self.path=self.root/'sample/process.json'
        self.cfg=read_json(self.path)
        self.cfg['generation_mode']='offline_subset'
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):write_json(self.path,self.cfg)
    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()):return run(self.path)
    def repin_test_file(self,path):
        """Authorize just an intentional test-input/baseline mutation in this disposable test."""
        manifest=read_json(self.root/'sample/baseline_manifest.json')
        manifest[path.relative_to(self.root/'sample').as_posix()]=digest(path.read_bytes())
        write_json(self.root/'sample/baseline_manifest.json',manifest)
    def baseline(self):return {p.relative_to(self.root).as_posix():digest(p.read_bytes()) for p in (self.root/'sample/cases').rglob('*') if p.is_file()}
    def test_all_jobs_generate_execute_and_match(self):
        baseline=self.baseline();result=self.execute()
        self.assertEqual(result['status'],'SYNTHETIC_TESTS_PASSED',result['issues'])
        self.assertEqual(result['metrics']['jobs_generated'],5)
        self.assertEqual(result['metrics']['steps'],6)
        self.assertEqual(result['metrics']['cases_passed'],3)
        self.assertEqual(sum(c['file_passed'] for c in result['cases']),18)
        self.assertEqual(sum(c['database_passed'] for c in result['cases']),3)
        self.assertEqual(self.baseline(),baseline)
        folder=Path(result['run_folder'])
        self.assertEqual(len(list((folder/'code').glob('*.py'))),5)
        self.assertTrue((folder/'ddl/local.sql').is_file())
        self.assertTrue((folder/'modernization_report.html').is_file())
    def test_unchanged_code_reused_but_database_recreated(self):
        first=self.execute();second=self.execute()
        self.assertEqual(second['status'],'SYNTHETIC_TESTS_PASSED')
        self.assertEqual(second['metrics']['cache_hits'],5)
        self.assertEqual(second['metrics']['new_generations'],0)
        self.assertNotEqual(first['run_folder'],second['run_folder'])
        with closing(sqlite3.connect(Path(second['run_folder'])/'cases/normal/local.sqlite')) as db:
            self.assertEqual(db.execute('select count(*) from ACCOUNT_LEDGER').fetchone()[0],7)
    def test_shared_copybook_change_invalidates_only_affected_jobs(self):
        self.execute()
        p=self.root/'sample/repository/copybooks/FEE.cpy'
        p.write_text(p.read_text()+'\n*> Dependency fingerprint changed; business behavior unchanged.\n')
        result=self.execute()
        self.assertEqual(result['status'],'SYNTHETIC_TESTS_PASSED')
        self.assertEqual(result['metrics']['cache_hits'],2)
        self.assertEqual(result['metrics']['new_generations'],3)
    def test_changed_source_changes_generated_code_and_fails_old_baseline(self):
        self.execute();before=self.baseline()
        p=self.root/'sample/repository/cobol/CLASSIFY.cbl'
        p.write_text(p.read_text().replace('>= 100000','>= 100001'))
        result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertEqual(result['metrics']['cache_hits'],4)
        self.assertIn("Decimal('100001')",(Path(result['run_folder'])/'code/JOB001.py').read_text())
        self.assertEqual(self.baseline(),before)
        self.assertIn('>= 100001',p.read_text())
    def test_missing_members_are_collected_not_asked_one_at_a_time(self):
        p=self.root/'sample/repository/cobol/CLASSIFY.cbl'
        p.write_text(p.read_text().replace('COPY ACCOUNT.','COPY ACCOUNT.\nCOPY MISSINGONE.\nCOPY MISSINGTWO.'))
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        missing=[q for q in result['issues'] if q['code']=='MISSING_MEMBER']
        self.assertEqual(len(missing),2)
        again=self.execute()
        self.assertEqual({q['id'] for q in missing},{q['id'] for q in again['issues'] if q['code']=='MISSING_MEMBER'})
    def test_changed_baseline_blocks_before_generation(self):
        p=self.root/'sample/cases/normal/expected/total.bin';p.write_bytes(b'changed')
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='BASELINE_INTEGRITY' for q in result['issues']))
        self.assertEqual(result['metrics']['jobs_generated'],0)
        self.assertEqual(p.read_bytes(),b'changed')
    def test_truncated_input_fails_without_being_repaired(self):
        p=self.root/'sample/cases/normal/inputs/raw.bin';p.write_bytes(p.read_bytes()[:-1]);self.repin_test_file(p)
        expected=p.read_bytes();result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertIn('partial record',result['cases'][0]['detail'])
        self.assertEqual(p.read_bytes(),expected)
    def test_duplicate_accounts_are_not_deduplicated(self):
        result=self.execute()
        with closing(sqlite3.connect(Path(result['run_folder'])/'cases/normal/local.sqlite')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM ACCOUNT_LEDGER WHERE ACCOUNT_ID='000002'").fetchone()[0],2)
    def test_wrong_database_expected_rows_are_detected(self):
        p=self.root/'sample/cases/normal/expected/database.json'
        data=read_json(p);data['ACCOUNT_LEDGER']['rows'].pop();write_json(p,data);self.repin_test_file(p)
        result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertEqual(result['cases'][0]['file_passed'],6)
        self.assertEqual(result['cases'][0]['database_passed'],0)
    def test_unsupported_sort_card_is_not_ignored(self):
        p=self.root/'sample/repository/jcl/JOB002.jcl'
        p.write_text(p.read_text().replace(' OPTION EQUALS',' OPTION EQUALS\n SUM FIELDS=NONE'))
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='AGENT_REQUIRED' and q['job']=='JOB002' for q in result['issues']))
        self.assertFalse(result['cases'])
    def test_cache_tampering_is_detected_not_regenerated(self):
        self.execute()
        target=next((self.root/'.migration/cache').glob('*/job.py'))
        target.write_text(target.read_text()+'\n# Deliberate corruption.\n')
        damaged=target.read_bytes();result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='CACHE_INTEGRITY' for q in result['issues']))
        self.assertEqual(target.read_bytes(),damaged)
    def test_missing_ddl_is_not_invented(self):
        (self.root/'sample/repository/ddl/ledger.sql').unlink()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='MISSING_DDL' for q in result['issues']))
    def test_output_path_escape_is_blocked(self):
        self.cfg['datasets']['SAMPLE.FEES']['path']='../escape.bin';self.save()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='UNSAFE_PATH' for q in result['issues']))
    def test_missing_output_baseline_cannot_be_counted_as_pass(self):
        del self.cfg['cases'][0]['expected_files']['SAMPLE.AUDIT'];self.save()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
    def test_existing_process_lock_prevents_overlapping_runs(self):
        output=self.root/'output';output.mkdir();(output/'.lock-synthetic_accounts').write_text('test lock')
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='RUN_LOCK' for q in result['issues']))
        self.assertTrue((output/'.lock-synthetic_accounts').exists())
    def test_conflicting_knowledge_blocks_reuse(self):
        answer={'id':'Q-1','scope':'synthetic_accounts','answer':'A','approved_by':'test SME','evidence':'test case','status':'approved'}
        other=dict(answer,answer='B')
        write_json(self.root/'knowledge/answers.json',{'schema_version':1,'answers':[answer,other]})
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='KNOWLEDGE' for q in result['issues']))
    def test_approved_knowledge_invalidates_generation_not_test_evidence(self):
        self.execute()
        answer={'id':'Q-1','scope':'synthetic_accounts','answer':'Category X has the documented exception.','approved_by':'test SME','evidence':'BASELINE_SPEC.md','status':'approved'}
        write_json(self.root/'knowledge/answers.json',{'schema_version':1,'answers':[answer]})
        result=self.execute()
        self.assertEqual(result['status'],'SYNTHETIC_TESTS_PASSED')
        self.assertEqual(result['metrics']['cache_hits'],0)
        self.assertEqual(result['metrics']['knowledge_answers'],1)
    def test_agent_mode_does_not_silently_use_offline_compiler(self):
        self.cfg['generation_mode']='agent';self.save()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        request=read_json(Path(result['run_folder'])/'agent_request.json')
        self.assertEqual(len(request['tasks']),5)
        self.assertFalse(result['cases'])
    def _prepare_agent_candidates(self):
        offline=self.execute()
        self.cfg['generation_mode']='agent';self.save()
        pending=self.execute()
        request_path=Path(pending['run_folder'])/'agent_request.json';request=read_json(request_path)
        for task in request['tasks']:
            trace={'job':task['job'],'unresolved':[],
                'source_coverage':[{'source':name,'start_line':1,'end_line':len((self.root/'sample/repository'/name).read_text().splitlines()),'target':'run'} for name in task['source_files']],
                'statements':read_json(Path(offline['run_folder'])/'code'/f'{task["job"]}.trace.json')['statements']}
            write_json(self.root/(task['job']+'.trace.json'),trace)
        return offline,request_path,request
    def test_agent_artifact_registration_contract_executes_sealed_code(self):
        offline,request_path,request=self._prepare_agent_candidates()
        self.assertEqual(len(request['tasks']),5)
        for task in request['tasks']:
            register(request_path,task['job'],Path(offline['run_folder'])/'code'/f'{task["job"]}.py',self.root/(task['job']+'.trace.json'))
        result=self.execute()
        self.assertEqual(result['status'],'SYNTHETIC_TESTS_PASSED')
        self.assertTrue(all(j['mode']=='sealed agent artifact' for j in result['jobs']))
    def test_agent_attempt_cannot_be_silently_replaced(self):
        offline,request_path,request=self._prepare_agent_candidates()
        task=request['tasks'][0];candidate=Path(offline['run_folder'])/'code'/f'{task["job"]}.py';trace=self.root/(task['job']+'.trace.json')
        register(request_path,task['job'],candidate,trace)
        changed=self.root/'changed.py';changed.write_text(candidate.read_text()+'\n# Different attempt.\n')
        with self.assertRaises(Blocked):register(request_path,task['job'],changed,trace)
    def test_stale_agent_request_is_rejected(self):
        offline,request_path,request=self._prepare_agent_candidates()
        p=self.root/'sample/repository/cobol/CLASSIFY.cbl';p.write_text(p.read_text()+'\n*> changed\n')
        task=request['tasks'][0]
        with self.assertRaises(Blocked):register(request_path,task['job'],Path(offline['run_folder'])/'code'/f'{task["job"]}.py',self.root/(task['job']+'.trace.json'))

    def test_called_working_storage_is_not_silently_reinitialized(self):
        p=self.root/'sample/repository/cobol/CALCFEE.cbl'
        p.write_text(p.read_text().replace('linkage section.', "working-storage section.\n01 SAVED-COUNT pic 9(6) value 0.\nlinkage section."))
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(q['code']=='AGENT_REQUIRED' for q in result['issues']))
    def test_stop_run_in_subprogram_is_not_treated_as_goback(self):
        p=self.root/'sample/repository/cobol/CALCFEE.cbl'
        p.write_text(p.read_text().replace('goback.','stop run.'))
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
    def test_database_failure_rolls_back_uncommitted_inserts(self):
        p=self.root/'sample/cases/normal/initial.sql'
        p.write_text(p.read_text()+"INSERT INTO ACCOUNT_LEDGER VALUES (2,'888888',2,20260901,'Z',0);\n")
        self.repin_test_file(p);result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        with closing(sqlite3.connect(Path(result['run_folder'])/'cases/normal/local.sqlite')) as db:
            self.assertEqual(db.execute('select SEQ from ACCOUNT_LEDGER order by SEQ').fetchall(),[(0,),(2,)])
    def test_incorrect_agent_code_is_reported_not_repaired(self):
        offline,request_path,request=self._prepare_agent_candidates()
        protected=self.baseline()
        for task in request['tasks']:
            candidate=Path(offline['run_folder'])/'code'/f'{task["job"]}.py'
            if task['job']=='JOB003':
                wrong=self.root/'wrong_fee.py'
                wrong.write_text(candidate.read_text().replace("Decimal('7')","Decimal('8')"));candidate=wrong
            register(request_path,task['job'],candidate,self.root/(task['job']+'.trace.json'))
        sealed=[p for p in (self.root/'agent_artifacts').glob('*/job.py') if "Decimal('8')" in p.read_text()]
        self.assertEqual(len(sealed),1);before=sealed[0].read_bytes()
        result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertEqual(sealed[0].read_bytes(),before)
        self.assertEqual(self.baseline(),protected)
        again=self.execute();self.assertEqual(again['status'],'VALIDATION_FAILED')
        self.assertEqual(again['metrics']['new_generations'],0)
    def test_agent_return_code_is_compared_not_ignored(self):
        offline,request_path,request=self._prepare_agent_candidates()
        for task in request['tasks']:
            candidate=Path(offline['run_folder'])/'code'/f'{task["job"]}.py'
            if task['job']=='JOB005':
                wrong=self.root/'wrong_rc.py'
                wrong.write_text(candidate.read_text()+"    return 4\n");candidate=wrong
            register(request_path,task['job'],candidate,self.root/(task['job']+'.trace.json'))
        result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertIn('return code',result['cases'][0]['detail'])
    def test_generated_source_mutation_is_detected(self):
        offline,request_path,request=self._prepare_agent_candidates()
        target=self.root/'sample/repository/cobol/CLASSIFY.cbl'
        for task in request['tasks']:
            candidate=Path(offline['run_folder'])/'code'/f'{task["job"]}.py'
            if task['job']=='JOB005':
                wrong=self.root/'source_writer.py'
                text=candidate.read_text()
                text+='    from pathlib import Path\n'
                text+=f'    p = Path({str(target)!r})\n'
                text+='    p.write_text(p.read_text()+"\\n*> unauthorized mutation\\n")\n'
                wrong.write_text(text);candidate=wrong
            register(request_path,task['job'],candidate,self.root/(task['job']+'.trace.json'))
        result=self.execute()
        self.assertEqual(result['status'],'INTEGRITY_FAILED')
        self.assertIn('unauthorized mutation',target.read_text())
    def test_worker_timeout_is_reported_without_retry(self):
        offline,request_path,request=self._prepare_agent_candidates()
        # Set the timeout BEFORE the request is created so the request is not stale.
        self.cfg['timeout_seconds']=1;self.cfg['cases']=self.cfg['cases'][:1];self.save()
        pending=self.execute();request_path=Path(pending['run_folder'])/'agent_request.json';request=read_json(request_path)
        for task in request['tasks']:
            candidate=Path(offline['run_folder'])/'code'/f'{task["job"]}.py'
            if task['job']=='JOB001':
                wrong=self.root/'infinite.py'
                wrong.write_text('"""Intentional timeout fault injection."""\ndef run(ctx):\n    """Never finish, to prove the timeout gate works."""\n    while True:\n        continue\n');candidate=wrong
            register(request_path,task['job'],candidate,self.root/(task['job']+'.trace.json'))
        result=self.execute()
        self.assertEqual(result['status'],'VALIDATION_FAILED')
        self.assertIn('time limit',result['cases'][0]['detail'])
    def test_real_baseline_cannot_use_synthetic_translation_backend(self):
        self.cfg['baseline']['kind']='mainframe';self.save()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')

    def test_discovery_still_runs_when_test_evidence_is_not_available(self):
        self.cfg['cases']=[];self.cfg['datasets']={};self.cfg['order_evidence']=''
        self.cfg['baseline']={'kind':'mainframe'};self.cfg['generation_mode']='agent';self.save()
        result=self.execute()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('run_folder',result)
        folder=Path(result['run_folder'])
        self.assertTrue((folder/'discovery.json').is_file())
        self.assertEqual(result['metrics']['jobs_discovered'],5)
        codes={q['code'] for q in result['issues']}
        self.assertIn('TEST_EVIDENCE',codes)
        self.assertIn('DATASET_BINDING',codes)
        self.assertIn('PROCESS_ORDER',codes)

if __name__=='__main__':unittest.main()
