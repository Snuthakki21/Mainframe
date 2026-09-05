"""Retargeting changes only its own layer and never edits previous deliveries."""
import contextlib,io,json,shutil,tempfile,unittest
from pathlib import Path
from migration.targets.controller import run,check_artifact
from migration.targets.config import load_target
from migration.common import write_json,read_json,digest,Blocked
ROOT=Path(__file__).resolve().parents[1]
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'sample',self.root/'sample');self.config=self.root/'sample/process.json'
        cfg=read_json(self.config);cfg['knowledge']=str(ROOT/'knowledge/answers.json');write_json(self.config,cfg)
        self.target=self.root/'target.json';write_json(self.target,load_target(ROOT/'target.json'))
    def tearDown(self):self.temp.cleanup()
    def runit(self,language='python',database='sqlite',verify=False):
        t=read_json(self.target);t.update(language=language,database=database);write_json(self.target,t)
        with contextlib.redirect_stdout(io.StringIO()):return run(self.config,self.target,verify=verify)
    def test_retarget_switch_and_switch_back_reuses_correct_layers(self):
        first=self.runit();self.assertEqual(first['metrics']['models_created'],5,first)
        oracle=self.runit(database='oracle');self.assertEqual(oracle['metrics']['models_reused'],5,oracle)
        self.assertEqual(oracle['metrics']['job_files_reused'],5)
        java=self.runit('java','oracle');self.assertEqual(java['metrics']['models_reused'],5)
        self.assertEqual(java['metrics']['job_files_created'],5)
        back=self.runit();self.assertTrue(back['metrics']['target_artifact_reused'])
        self.assertEqual(first['artifact_id'],back['artifact_id'])
        self.assertEqual(oracle['verification']['native_database'],'NOT_RUN')
        history=read_json(Path(back['registry_file']))['history'];self.assertEqual(len(history),4)
    def test_corrupted_prior_artifact_is_blocked_without_repair(self):
        first=self.runit();p=Path(first['artifact_folder'])/'jobs/JOB001.py';original=p.read_text();p.write_text(original+'\n# changed\n')
        second=self.runit();self.assertEqual(second['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='ARTIFACT_INTEGRITY' for i in second['issues']))
        self.assertEqual(p.read_text(),original+'\n# changed\n')
    def test_changed_source_invalidates_only_affected_job_model(self):
        self.runit();p=self.root/'sample/repository/cobol/CLASSIFY.cbl';original=p.read_text();self.assertIn('C-AMOUNT >= 100000',original);p.write_text(original.replace('C-AMOUNT >= 100000','C-AMOUNT >= 100001'))
        second=self.runit();self.assertEqual(second['metrics']['models_created'],1,second)
        self.assertEqual(second['metrics']['job_files_reused'],4)
    def test_bigquery_pk_blocker_prevents_validated_status(self):
        result=self.runit(database='bigquery');self.assertEqual(result['status'],'GENERATED_WITH_CAPABILITY_BLOCKERS',result)
        self.assertNotEqual(result['verification']['native_database'],'PASSED')
    def test_conflicting_process_target_is_rejected(self):
        cfg=read_json(self.config);cfg['target']='java';write_json(self.config,cfg)
        result=self.runit();self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='TARGET_CONFIG' for i in result['issues']))
    def test_baseline_tamper_blocks_even_when_target_changed(self):
        self.runit();p=self.root/'sample/cases/normal/expected/fees.bin';p.write_bytes(b'bad')
        result=self.runit('java','oracle');self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='BASELINE_INTEGRITY' for i in result['issues']))
    def test_registry_tamper_blocks_instead_of_resetting_history(self):
        first=self.runit();p=Path(first['registry_file']);d=read_json(p);d['history'][0]['status']='FORGED_PASS';write_json(p,d)
        result=self.runit();self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='REGISTRY_INTEGRITY' for i in result['issues']))
    def test_legacy_delivery_is_recorded_without_inheriting_validation(self):
        p=self.root/'output/synthetic_accounts/old-v1';(p/'code').mkdir(parents=True)
        write_json(p/'result.json',{'status':'SYNTHETIC_TESTS_PASSED'});(p/'code/JOB001.py').write_text('"Legacy original."\n')
        result=self.runit('java','oracle');registry=read_json(Path(result['registry_file']))
        self.assertEqual(len(registry['legacy_deliveries']),1)
        self.assertIn('RECORDED_LEGACY',registry['legacy_deliveries'][0]['reuse_status'])
        self.assertNotEqual(result['verification']['native_database'],'PASSED')
if __name__=='__main__':unittest.main()
