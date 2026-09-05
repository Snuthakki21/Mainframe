"""All target pairs must use source-driven native code, not renamed Python."""
import json,unittest
from pathlib import Path
from migration.discovery import discover
from migration.inventory import read_inventory
from migration.targets.model import extract
from migration.targets.emit import emit_job
ROOT=Path(__file__).resolve().parents[1]
class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg=json.loads((ROOT/'sample/process.json').read_text())
        d=discover(ROOT/'sample/repository',read_inventory(ROOT/'sample/inventory.xlsx','Process'),cfg)
        cls.models=[extract(j,d['index'],'free') for j in d['jobs']]
    def test_python_source_condition_is_emitted(self):
        text=emit_job(self.models[0],'python');self.assertIn("Decimal('100000')",text)
        compile(text,'JOB001.py','exec')
    def test_java_has_native_methods_and_not_python_execution(self):
        text=emit_job(self.models[0],'java');self.assertIn('public static void run',text)
        self.assertIn('new BigDecimal("100000")',text);self.assertNotIn('ProcessBuilder',text)
    def test_csharp_has_native_methods(self):
        text=emit_job(self.models[0],'dotnet');self.assertIn('public static void run',text)
        self.assertIn('Dec.Parse("100000")',text);self.assertNotIn('python',text.lower())
    def test_multistep_job_retained_for_all_languages(self):
        m=next(m for m in self.models if len(m['steps'])==2)
        for lang in ('python','java','dotnet'):
            text=emit_job(m,lang)
            for s in m['steps']:self.assertIn('step_'+s['name'],text)
    def test_no_unfinished_implementation_marker(self):
        for m in self.models:
            for lang in ('python','java','dotnet'):
                text=emit_job(m,lang)
                for bad in ('TODO','NotImplementedException','NotImplementedError','FIXME'):
                    self.assertNotIn(bad,text)
