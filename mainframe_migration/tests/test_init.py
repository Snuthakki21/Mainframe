"""Exercise operator setup with real files and persisted destination choices."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import modernize


ROOT = Path(__file__).resolve().parents[1]


class InitializationTests(unittest.TestCase):
    def test_markdown_setup_ignores_sheet_and_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'process.json'
            inventory = root / 'flow.md'
            inventory.write_text('# Job: JOB001\n| Step | Program | Description |\n'
                                 '| --- | --- | --- |\n| CLASSIFY | CLASSIFY | Classify accounts |\n')
            arguments = ['init', '--repository', str(ROOT / 'sample/repository'),
                         '--inventory', str(inventory), '--sheet', 'Ignored for Markdown',
                         '--process', 'MARKDOWN', '--config', str(config),
                         '--output', str(root / 'output'), '--source-format', 'free']
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(modernize.main(arguments), 2)
            original = config.read_bytes()
            saved = json.loads(original)
            self.assertNotIn('sheet', saved)
            self.assertEqual(saved['inventory'], str(inventory.resolve()))
            self.assertEqual(saved['execution_order'], ['JOB001'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(modernize.main(arguments), 2)
            self.assertEqual(config.read_bytes(), original)

    def test_init_persists_output_and_target_then_leaves_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'process.json'
            output = root / 'deliverables'
            target = root / 'target.json'
            target.write_bytes((ROOT / 'target.json').read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):
                code = modernize.main([
                    'init', '--repository', str(ROOT / 'sample/repository'),
                    '--inventory', str(ROOT / 'sample/inventory.xlsx'),
                    '--process', 'ACCOUNTS', '--config', str(config),
                    '--source-format', 'free', '--output', str(output),
                    '--target', str(target),
                ])
            self.assertEqual(code, 2)  # Real-process setup has no evidence/bindings yet.
            saved = json.loads(config.read_text())
            self.assertEqual(saved['output'], str(output.resolve()))
            self.assertEqual(saved['target_file'], str(target.resolve()))
            self.assertEqual(saved['sheet'], 'Process')
            self.assertTrue((output / 'ACCOUNTS/modernization_report.html').is_file())
            result = json.loads((output / 'ACCOUNTS/latest_result.json').read_text())
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertTrue(list((output / 'ACCOUNTS/runs').glob('*/agent_request.json')))

    def test_invalid_process_does_not_leave_unusable_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'process.json'
            with contextlib.redirect_stdout(io.StringIO()):
                code = modernize.main([
                    'init', '--repository', str(ROOT / 'sample/repository'),
                    '--inventory', str(ROOT / 'sample/inventory.xlsx'),
                    '--process', '../ACCOUNTS', '--config', str(config),
                ])
            self.assertEqual(code, 2)
            self.assertFalse(config.exists())


if __name__ == '__main__':
    unittest.main()
