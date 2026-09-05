"""Configuration is tested before a target can affect generated output."""
import copy,json,tempfile,unittest
from pathlib import Path
from migration.common import Blocked
from migration.targets.config import load_target
ROOT=Path(__file__).resolve().parents[1]
class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'target.json'
        self.cfg=json.loads((ROOT/'target.json').read_text())
    def tearDown(self):self.tmp.cleanup()
    def load(self):self.path.write_text(json.dumps(self.cfg));return load_target(self.path)
    def test_python_sqlite_default(self):
        t=self.load();self.assertEqual((t['language'],t['database']),('python','sqlite'))
    def test_dotnet_alias_is_canonical(self):
        self.cfg['language']='.NET';self.assertEqual(self.load()['language'],'dotnet')
    def test_gcp_is_not_a_database(self):
        self.cfg['database']='GCP'
        with self.assertRaisesRegex(Blocked,'bigquery'):self.load()
    def test_unknown_language_never_falls_back(self):
        self.cfg['language']='javva'
        with self.assertRaises(Blocked):self.load()
    def test_unknown_key_never_ignored(self):
        self.cfg['databse']='oracle'
        with self.assertRaises(Blocked):self.load()
    def test_duplicate_keys_rejected(self):
        self.path.write_text('{"schema_version":1,"language":"python","language":"java","database":"sqlite"}')
        with self.assertRaisesRegex(Blocked,'Duplicate'):load_target(self.path)
    def test_connection_secrets_are_not_inline(self):
        self.cfg['connections']['oracle']['password']='secret'
        with self.assertRaises(Blocked):self.load()
    def test_framework_version_is_validated(self):
        self.cfg['versions']['dotnet_framework']='net2.0'
        with self.assertRaises(Blocked):self.load()
