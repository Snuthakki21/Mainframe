"""Source provenance must survive Windows separators without becoming Python code."""
import ast
import copy
from pathlib import Path
import unittest
import warnings

from migration.compiler import compile_job, emit_program
from migration.discovery import discover
from migration.inventory import read_inventory
from migration.targets.emit import emit_job
from migration.targets.model import extract


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAMES = (
    r'jcl\JOB001.jcl',
    r'jcl\Users\JOB001.jcl',
    r'jcl\new\test\JOB001.jcl',
    'jcl/"""quoted"""/JOB001.jcl',
)


class SourcePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = ROOT / 'sample/repository'
        cls.found = discover(cls.repository, read_inventory(ROOT / 'sample/process.md'),
                             {'source_format': 'free'})
        cls.job = cls.found['jobs'][0]
        cls.model = extract(cls.job, cls.found['index'], 'free')

    def compile_without_escape_warnings(self, emit):
        # Python versions categorize invalid escapes differently; both must fail.
        with warnings.catch_warnings():
            warnings.simplefilter('error', SyntaxWarning)
            warnings.simplefilter('error', DeprecationWarning)
            code = emit()
            compile(code, 'generated_job.py', 'exec')
            return ast.parse(code)

    def test_legacy_module_docstring_preserves_windows_source_path(self):
        for source in SOURCE_NAMES:
            with self.subTest(source=source):
                job = copy.deepcopy(self.job)
                job['source'] = source
                tree = self.compile_without_escape_warnings(
                    lambda: compile_job(job, self.found['index'], 'free')[0])
                self.assertIn('Source JCL: ' + source, ast.get_docstring(tree))

    def test_target_module_docstring_preserves_windows_source_path(self):
        for source in SOURCE_NAMES:
            with self.subTest(source=source):
                model = copy.deepcopy(self.model)
                model['source'] = source
                tree = self.compile_without_escape_warnings(lambda: emit_job(model, 'python'))
                self.assertIn('Source: ' + source, ast.get_docstring(tree))

    def test_program_docstring_preserves_backslashes_and_quotes(self):
        for source in SOURCE_NAMES:
            with self.subTest(source=source):
                program = copy.deepcopy(self.model['programs'][0])
                program['source'] = source
                tree = self.compile_without_escape_warnings(lambda: '\n'.join(emit_program(program)))
                self.assertIn(' from ' + source + ';', ast.get_docstring(tree.body[0]))

    def test_discovered_sources_remain_portable_repository_relative_paths(self):
        self.assertEqual(self.job['source'], 'jcl/JOB001.jcl')
        self.assertEqual(self.job['dependencies'], [
            'cobol/CLASSIFY.cbl', 'copybooks/ACCOUNT.cpy', 'jcl/JOB001.jcl'])
        for source in self.found['sources']:
            self.assertNotIn('\\', source)
            self.assertFalse(Path(source).is_absolute())
            self.assertTrue((self.repository / source).is_file())


if __name__ == '__main__':
    unittest.main()
