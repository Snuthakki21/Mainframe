"""These test the handoff contract, not a live Copilot or Devin session."""
import contextlib,io,json,shutil,tempfile,unittest
from pathlib import Path
from migration.common import Blocked,read_json,write_json
from migration.targets.controller import run
from migration.targets.agent import register
from migration.targets.package import assemble
from migration.targets.model import extract
from migration.targets.config import load_target
from migration.discovery import discover
from migration.inventory import read_inventory
ROOT=Path(__file__).resolve().parents[1]
class AgentTargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'sample',self.root/'sample');self.cfg=read_json(self.root/'sample/process.json')
        self.cfg['generation_mode']='agent';self.cfg['knowledge']=str(ROOT/'knowledge/answers.json');write_json(self.root/'sample/process.json',self.cfg)
        self.target=load_target(ROOT/'target.json');write_json(self.root/'target.json',self.target)
    def tearDown(self):self.tmp.cleanup()
    def runit(self):
        with contextlib.redirect_stdout(io.StringIO()):return run(self.root/'sample/process.json',self.root/'target.json',verify=False)
    def candidate(self):
        result=self.runit();self.assertEqual(result['status'],'BLOCKED')
        request_path=Path(result['run_folder'])/'agent_request.json';request=read_json(request_path)
        d=discover(self.root/'sample/repository',read_inventory(self.root/'sample/inventory.xlsx','Process'),self.cfg)
        models=[extract(j,d['index'],'free') for j in d['jobs']]
        files,payload=assemble(models,request['schema'],self.cfg,self.target)
        candidate=self.root/'candidate';candidate.mkdir()
        for name,text in files.items():
            p=candidate/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        review={'request_id':request['request_id'],'reviewer':'automated test fixture; not a live coding agent',
                'method':'agent_self_review','unresolved_fidelity_findings':[],'jobs':{}}
        for j in d['jobs']:
            review['jobs'][j['name']]={'source_paths':j['dependencies'],'trace':[{'source':j['source'],'source_line':1,'generated_file':'jobs/'+j['name']+'.py','generated_line':1,'intent':'Execute the source job in order.'}]}
        rp=self.root/'review.json';write_json(rp,review);return request_path,candidate,rp
    def test_registered_candidate_is_consumed_without_repair_or_claiming_live_ai(self):
        req,cand,review=self.candidate();register(req,cand,review)
        result=self.runit();self.assertEqual(result['status'],'GENERATED_NOT_FULLY_VALIDATED',result)
        self.assertEqual(result['metrics']['registered_job_files'],5)
        self.assertEqual(result['agent_review']['method'],'agent_self_review')
    def test_candidate_for_different_database_is_rejected(self):
        req,cand,review=self.candidate();p=cand/'target.json';t=read_json(p);t['database']='oracle';write_json(p,t)
        with self.assertRaises(Blocked):register(req,cand,review)
    def test_changed_source_makes_registration_stale(self):
        req,cand,review=self.candidate();p=self.root/'sample/repository/cobol/CLASSIFY.cbl';p.write_text(p.read_text()+'\n*> changed source\n')
        with self.assertRaises(Blocked):register(req,cand,review)
    def test_sealed_agent_candidate_cannot_be_overwritten(self):
        req,cand,review=self.candidate();register(req,cand,review)
        p=cand/'jobs/JOB001.py';p.write_text(p.read_text()+'\n# changed delivery\n')
        with self.assertRaises(Blocked):register(req,cand,review)
    def test_stale_target_request_is_rejected(self):
        req,cand,review=self.candidate();p=self.root/'target.json';t=read_json(p);t['language']='java';write_json(p,t)
        with self.assertRaises(Blocked):register(req,cand,review)
    def test_invented_source_location_is_rejected(self):
        req,cand,review=self.candidate();r=read_json(review);r['jobs']['JOB001']['trace'][0]['source_line']=999999;write_json(review,r)
        with self.assertRaises(Blocked):register(req,cand,review)
if __name__=='__main__':unittest.main()
