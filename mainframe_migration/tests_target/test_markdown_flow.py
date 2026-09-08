"""Exercise documented Markdown through discovery, handoff, and native validation."""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from migration.common import Blocked, read_json, write_json
from migration.inventory import read_inventory
from migration.discovery import discover
from migration.targets.agent import check_request
from migration.targets.config import load_target
from migration.targets.controller import run, check_artifact

ROOT = Path(__file__).resolve().parents[1]
FLOW = """# Synthetic accounts job flow

Source: inventory.xlsx (one-time conversion)

# Job: JOB001

## Input qualification

| Step | Program | Input | Output |
| --- | --- | --- | --- |
| STEP0 | NONE | NONE | NONE |
| S010 | CLASSIFY | SAMPLE.RAW; SAMPLE.BDATE | SAMPLE.ACCEPT; SAMPLE.REJECT |

# Job: JOB002

| Step | Program | Input | Output |
| --- | --- | --- | --- |
| S010 | SORT | SAMPLE.ACCEPT | SAMPLE.SORTED |

# Job: JOB003

## Fee processing

| Step | Program | Input | Output | Description |
| --- | --- | --- | --- | --- |
| S010 | FEEPOST | SAMPLE.SORTED | SAMPLE.FEES | Preserve source fees and rejects. |

# Job: JOB004

## Audit and ledger

| Step | Program | Input | Output |
| --- | --- | --- | --- |
| S010 | IEBGENER | SAMPLE.FEES | SAMPLE.AUDIT |

| Step | Program | Description |
| --- | --- | --- |
| S020 | LOADDB | Load the ledger with source commit behavior. |

# Job: JOB005

| Step | Program | Input | Output |
| --- | --- | --- | --- |
| S010 | TOTALS | SAMPLE.FEES | SAMPLE.TOTAL |
"""


class MarkdownFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT/'sample', self.root/'sample')
        self.config = self.root/'sample/process.json'
        self.cfg = read_json(self.config)
        self.cfg['inventory'] = 'process.md'
        self.cfg['knowledge'] = str(ROOT/'knowledge/answers.json')
        write_json(self.config, self.cfg)
        self.document = self.root/'sample/process.md'
        self.document.write_text(FLOW, encoding='utf-8')
        self.target = self.root/'target.json'
        write_json(self.target, load_target(ROOT/'target.json'))

    def tearDown(self):
        self.tmp.cleanup()

    def runit(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(self.config, self.target, **kwargs)

    def test_markdown_executes_python_sqlite_and_preserves_report_provenance(self):
        result = self.runit()
        self.assertEqual(result['status'], 'SYNTHETIC_TARGET_VALIDATED', result)
        self.assertEqual(result['verification']['native_database'], 'PASSED')
        self.assertEqual(sum(c['file_passed'] for c in result['verification']['cases']), 18)
        self.assertEqual(sum(c['database_passed'] for c in result['verification']['cases']), 3)
        self.assertEqual(sum(c['rc_passed'] for c in result['verification']['cases']), 15)
        flow = read_json(Path(result['process_flow_file']))
        self.assertEqual(flow, result['process_flow'])
        self.assertEqual(flow['documented_job_order'], self.cfg['execution_order'])
        marker = flow['rows'][0]
        self.assertTrue(marker['documentation_only'])
        self.assertEqual(marker['kind'], 'DOCUMENTATION_ONLY')
        description_row = next(r for r in flow['rows'] if r['program'] == 'LOADDB')
        self.assertFalse(description_row['documentation_only'])
        self.assertEqual(description_row['section'], 'Audit and ledger')
        self.assertEqual(description_row['fields_present'], ['step', 'program', 'description'])
        self.assertEqual(FLOW.splitlines()[description_row['row']-1].split('|')[2].strip(), 'LOADDB')
        self.assertEqual(description_row['source'], str(self.document.resolve()))
        audit = next(d for d in flow['dataset_bindings'] if d['dataset'] == 'SAMPLE.AUDIT')
        self.assertEqual((audit['path'], audit['configured_role']), ('files/audit.bin', 'output'))
        self.assertEqual(audit['documented_outputs'][0]['job'], 'JOB004')
        self.assertEqual(audit['jcl_references'][0]['dd'], 'SYSUT2')
        report = (Path(result['run_folder'])/'modernization_report.html').read_text()
        for evidence in ('Input qualification', 'Load the ledger', 'files/audit.bin', 'DOCUMENTATION_ONLY'):
            self.assertIn(evidence, report)
        check_artifact(Path(result['artifact_folder']))

    def test_agent_request_retains_document_and_missing_source_gaps(self):
        self.cfg['generation_mode'] = 'agent'
        write_json(self.config, self.cfg)
        (self.root/'sample/repository/cobol/CLASSIFY.cbl').unlink()
        result = self.runit(verify=False)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any(i['code'] == 'MISSING_MEMBER' for i in result['issues']))
        self.assertFalse(any('NONE is referenced' in i['question'] for i in result['issues']))
        request = read_json(Path(result['run_folder'])/'agent_request.json')
        self.assertEqual(request['process_flow'], result['process_flow'])
        self.assertIn(str(self.document.resolve()), request['input_files'])
        self.assertTrue(any(i['code'] == 'MISSING_MEMBER' for i in request['discovery_issues']))
        self.assertNotIn('artifact_folder', result)

    def test_editing_markdown_invalidates_agent_registration_request(self):
        self.cfg['generation_mode'] = 'agent'
        write_json(self.config, self.cfg)
        result = self.runit(verify=False)
        request = read_json(Path(result['run_folder'])/'agent_request.json')
        check_request(request)
        self.document.write_text(FLOW.replace('source fees', 'source fee policy'), encoding='utf-8')
        with self.assertRaises(Blocked) as caught:
            check_request(request)
        self.assertEqual(caught.exception.code, 'AGENT_INPUT_CHANGED')
        updated = self.runit(verify=False)
        updated_request = read_json(Path(updated['run_folder'])/'agent_request.json')
        self.assertNotEqual(request['request_id'], updated_request['request_id'])

    def test_description_changes_reuse_source_models_without_carrying_validation(self):
        first = self.runit(verify=False)
        self.assertEqual(first['verification']['generation'], 'PASSED', first)
        self.document.write_text(FLOW.replace('source fees', 'documented source fees'), encoding='utf-8')
        second = self.runit(verify=False)
        self.assertEqual(second['metrics']['models_reused'], 5, second)
        self.assertEqual(second['artifact_id'], first['artifact_id'])
        self.assertEqual(second['verification']['native_database'], 'NOT_RUN')
        self.assertNotEqual(first['process_flow']['inventory']['sha256'], second['process_flow']['inventory']['sha256'])

    def test_new_knowledge_file_invalidates_request_that_recorded_its_absence(self):
        self.cfg['generation_mode'] = 'agent'
        self.cfg['knowledge'] = 'knowledge/new_answers.json'
        write_json(self.config, self.cfg)
        result = self.runit(verify=False)
        request = read_json(Path(result['run_folder'])/'agent_request.json')
        knowledge = self.root/'sample/knowledge/new_answers.json'
        self.assertIn(str(knowledge.resolve()), request['input_files'])
        self.assertIsNone(request['input_files'][str(knowledge.resolve())])
        check_request(request)
        write_json(knowledge, {'schema_version': 1, 'answers': []})
        with self.assertRaises(Blocked) as caught:
            check_request(request)
        self.assertEqual(caught.exception.code, 'AGENT_INPUT_CHANGED')

    def test_documented_dataset_mismatch_blocks_without_inventing_a_destination(self):
        self.document.write_text(FLOW.replace('SAMPLE.TOTAL |', 'UNKNOWN.TOTAL |'), encoding='utf-8')
        result = self.runit(verify=False)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any(i['code'] == 'INVENTORY_DATASET_CONFLICT' for i in result['issues']))
        binding = next(d for d in result['process_flow']['dataset_bindings'] if d['dataset'] == 'UNKNOWN.TOTAL')
        self.assertEqual(binding['destination_status'], 'UNRESOLVED')
        self.assertIsNone(binding['path'])
        self.assertNotIn('artifact_folder', result)

    def test_unbound_declared_output_remains_explicit_on_discovery(self):
        del self.cfg['datasets']['SAMPLE.TOTAL']
        write_json(self.config, self.cfg)
        result = self.runit(discover_only=True)
        self.assertEqual(result['status'], 'DISCOVERED_WITH_GAPS')
        self.assertTrue(any(i['code'] == 'DATASET_BINDING' for i in result['issues']))
        binding = next(d for d in result['process_flow']['dataset_bindings'] if d['dataset'] == 'SAMPLE.TOTAL')
        self.assertIsNone(binding['path'])
        self.assertEqual(binding['destination_status'], 'UNRESOLVED')

    def test_description_is_not_used_to_invent_dataset_declarations(self):
        self.document.write_text(FLOW.replace('Load the ledger with source commit behavior.', 'Load FAKE.OUTPUT into invented/path.bin.'), encoding='utf-8')
        result = self.runit(discover_only=True)
        self.assertEqual(result['status'], 'DISCOVERED', result)
        self.assertNotIn('FAKE.OUTPUT', {d['dataset'] for d in result['process_flow']['dataset_bindings']})

    def test_table_output_is_checked_against_source_ddl_not_jcl_dds(self):
        document = FLOW.replace('| Step | Program | Description |\n| --- | --- | --- |\n| S020 | LOADDB | Load the ledger with source commit behavior. |',
                                '| Step | Program | Output |\n| --- | --- | --- |\n| S020 | LOADDB | TABLE:ACCOUNT_LEDGER |')
        self.document.write_text(document, encoding='utf-8')
        result = self.runit(discover_only=True)
        self.assertEqual(result['status'], 'DISCOVERED', result)
        obj = result['process_flow']['database_objects'][0]
        self.assertEqual((obj['name'], obj['schema_status']), ('ACCOUNT_LEDGER', 'SOURCE_DDL'))
        self.assertNotIn('TABLE:ACCOUNT_LEDGER', {d['dataset'] for d in result['process_flow']['dataset_bindings']})

    def test_io_membership_does_not_guess_direction_from_disp(self):
        rows = read_inventory(self.document)
        row = next(r for r in rows if r['program'] == 'CLASSIFY')
        row['inputs'] = ['SAMPLE.ACCEPT']  # DISP cannot establish source I/O direction.
        row['outputs'] = []
        result = discover(self.root/'sample/repository', rows, self.cfg)
        self.assertEqual(result['issues'], [])

    def test_table_used_by_another_step_cannot_be_claimed_as_this_steps_output(self):
        self.document.write_text(FLOW.replace('SAMPLE.TOTAL |', 'TABLE:ACCOUNT_LEDGER |'), encoding='utf-8')
        result = self.runit(verify=False)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any(i['code'] == 'INVENTORY_DATABASE_CONFLICT' and i['job'] == 'JOB005'
                            for i in result['issues']))
        self.assertNotIn('artifact_folder', result)

    def test_no_program_row_with_dataset_work_cannot_be_silently_dropped(self):
        self.document.write_text(FLOW.replace('| STEP0 | NONE | NONE | NONE |', '| STEP0 | NONE | NONE | SAMPLE.ACCEPT |'), encoding='utf-8')
        result = self.runit(verify=False)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['verification']['generation'], 'NOT_RUN')

    def test_malformed_document_cannot_report_generation_success(self):
        self.document.write_text('# Job: JOB001\n\n| Step | Program |\n| --- | --- |\n| S010 |\n', encoding='utf-8')
        result = self.runit(verify=False)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any(i['code'] == 'INVENTORY' for i in result['issues']))
        self.assertEqual(result['verification']['generation'], 'NOT_RUN')
        self.assertNotIn('artifact_folder', result)


if __name__ == '__main__':
    unittest.main()
