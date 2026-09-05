"""Prove that target validation never borrows another database's pass status."""
import json, tempfile, unittest, shutil, contextlib, io
from pathlib import Path
from unittest.mock import patch
from migration.targets.verify import verify_target
from migration.targets.config import load_target
from migration.targets.package import assemble
from migration.targets.model import extract
from migration.targets.schema import parse_schema
from migration.runner import load_config
from migration.discovery import discover
from migration.inventory import read_inventory
ROOT=Path(__file__).resolve().parents[1]

class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg,cls.paths=load_config(ROOT/'sample/process.json')
        d=discover(cls.paths['repo'],read_inventory(cls.paths['inventory'],'Process'),cls.cfg)
        cls.models=[extract(j,d['index'],'free') for j in d['jobs']]
        cls.schema=parse_schema((cls.paths['repo']/'ddl/ledger.sql').read_text())
    def build(self,root,language,database):
        target=load_target(ROOT/'target.json');target.update(language=language,database=database)
        files,payload=assemble(self.models,self.schema,self.cfg,target)
        artifact=root/'artifact';artifact.mkdir()
        for name,text in files.items():
            p=artifact/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
        return artifact,payload,target
    def test_python_sqlite_executes_real_sqlite_and_matches_all_scenarios(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,p,t=self.build(root,'python','sqlite')
            result=verify_target(a,root/'verify',self.cfg,self.paths,p,t,True,False)
            self.assertFalse(result['failed'],result)
            self.assertEqual(result['native_database'],'PASSED')
            self.assertEqual(sum(c['file_passed'] for c in result['cases']),18)
            self.assertEqual(sum(c['database_passed'] for c in result['cases']),3)
            self.assertEqual(sum(c['rc_passed'] for c in result['cases']),15)
    def test_oracle_is_explicit_contract_not_a_live_database_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,p,t=self.build(root,'python','oracle')
            result=verify_target(a,root/'verify',self.cfg,self.paths,p,t,True,False)
            self.assertFalse(result['failed'],result)
            self.assertEqual(result['contract_execution'],'PASSED')
            self.assertEqual(result['native_database'],'NOT_RUN_REMOTE')
    def test_missing_dotnet_sdk_cannot_report_compiled_or_validated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,p,t=self.build(root,'dotnet','sqlite')
            with patch('migration.targets.verify.shutil.which',return_value=None):
                result=verify_target(a,root/'verify',self.cfg,self.paths,p,t,True,False)
            self.assertEqual(result['compilation'],'NOT_AVAILABLE')
            self.assertEqual(result['cases'],[])
            self.assertNotEqual(result['native_database'],'PASSED')
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'Native Java mutation check needs an installed JDK')
    def test_native_java_source_change_fails_unchanged_baseline_without_repair(self):
        from migration.targets.controller import run,check_artifact
        from migration.common import read_json,write_json,digest
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);shutil.copytree(ROOT/'sample',root/'sample')
            config=root/'sample/process.json';cfg=read_json(config);cfg['knowledge']=str(ROOT/'knowledge/answers.json');write_json(config,cfg)
            source=root/'sample/repository/cobol/CLASSIFY.cbl';text=source.read_text();self.assertIn('>= 100000',text);source.write_text(text.replace('>= 100000','>= 100001'))
            target=load_target(ROOT/'target.json');target['language']='java';write_json(root/'target.json',target)
            expected=root/'sample/cases/boundaries/expected/fees.bin';before=digest(expected.read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):result=run(config,root/'target.json')
            self.assertEqual(result['status'],'VALIDATION_FAILED',result)
            self.assertEqual(digest(expected.read_bytes()),before)
            self.assertEqual(source.read_text(),text.replace('>= 100000','>= 100001'))
            check_artifact(Path(result['artifact_folder']))

    def test_no_baseline_still_compiles_but_does_not_validate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,p,t=self.build(root,'python','sqlite')
            result=verify_target(a,root/'verify',self.cfg,self.paths,p,t,False,False)
            self.assertEqual(result['compilation'],'PASSED')
            self.assertEqual(result['cases'],[])
            self.assertEqual(result['native_database'],'NOT_RUN_NO_BASELINE')

if __name__=='__main__':unittest.main()
