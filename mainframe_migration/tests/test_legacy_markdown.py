"""The retained Python runner must keep the same documented flow and destinations."""
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest

from migration.common import read_json, write_json
from migration.inventory import read_inventory
from migration.runner import run

ROOT = Path(__file__).resolve().parents[1]


class LegacyMarkdownTests(unittest.TestCase):
    def test_full_legacy_flow_retains_documentation_and_validates_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'sample', root / 'sample')
            config = root / 'sample/process.json'
            cfg = read_json(config)
            cfg['inventory'] = 'process.md'
            cfg.pop('sheet', None)
            write_json(config, cfg)
            rows = read_inventory(ROOT / 'sample/inventory.xlsx')
            lines = ['# Job: JOB001', '## Classification',
                     '| Step | Program | Input | Output | Description |',
                     '| --- | --- | --- | --- | --- |',
                     '| STEP0 | NONE | NONE | NONE | Documentation marker |']
            job = 'JOB001'
            for row in rows:
                if row['job'] != job:
                    job = row['job']
                    lines += ['', '# Job: ' + job,
                              '| Step | Program | Input | Output | Description |',
                              '| --- | --- | --- | --- | --- |']
                lines.append('| ' + ' | '.join([
                    row['step'], row['program'], '; '.join(row['inputs']),
                    '; '.join(row['outputs']), 'Source-backed sample step',
                ]) + ' |')
            (root / 'sample/process.md').write_text('\n'.join(lines) + '\n')
            with contextlib.redirect_stdout(io.StringIO()):
                result = run(config)
            self.assertEqual(result['status'], 'SYNTHETIC_TESTS_PASSED', result['issues'])
            folder = Path(result['run_folder'])
            flow = read_json(folder / 'process_flow.json')
            self.assertEqual(len(flow['rows']), 7)
            self.assertTrue(flow['rows'][0]['documentation_only'])
            self.assertEqual(flow['rows'][1]['section'], 'Classification')
            self.assertEqual(flow['inventory']['format'], 'md')
            bindings = {b['dataset']: b for b in flow['dataset_bindings']}
            self.assertEqual(bindings['SAMPLE.TOTAL']['path'], 'files/total.bin')
            self.assertEqual(flow['database_objects'][0]['name'], 'ACCOUNT_LEDGER')
            self.assertEqual(flow['database_objects'][0]['schema_status'], 'SOURCE_DDL')
            report = (folder / 'modernization_report.html').read_text()
            self.assertIn('Classification', report)
            self.assertIn('files/total.bin', report)
            self.assertEqual(read_json(folder / 'agent_request.json')['process_flow'], flow)


if __name__ == '__main__':
    unittest.main()
