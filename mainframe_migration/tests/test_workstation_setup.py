"""Run the delivered CLI in a disposable, package-free workstation layout.

These are actual Python/SQLite subprocess checks on the current operating system,
not a claim that Windows policy, a mainframe, or an IDE agent was exercised. The
source and frozen synthetic expectations are copied unchanged from the sample.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import venv


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


class WorkstationSetupTests(unittest.TestCase):
    """Exercise paths, deployment assembly, fresh evidence, and CLI stop conditions."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='migration workstation ')
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'Common parent with spaces'
        self.workspace.mkdir()
        self.set_paths()
        self.framework.mkdir()
        for name in ('modernize.py', 'target.json', 'AGENTS.md'):
            shutil.copy2(ROOT / name, self.framework / name)
        for name in ('migration', 'knowledge', '.agents'):
            shutil.copytree(ROOT / name, self.framework / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'sample/repository', self.source)
        self.inventory.parent.mkdir()
        shutil.copy2(ROOT / 'sample/process.md', self.inventory)
        self.config.parent.mkdir(parents=True)
        shutil.copytree(ROOT / 'sample/cases', self.config.parent / 'cases')
        shutil.copy2(ROOT / 'sample/baseline_manifest.json',
                     self.config.parent / 'baseline_manifest.json')
        self.config_data = read_json(ROOT / 'sample/process.json')
        for key, path in {
            'repository': self.source,
            'inventory': self.inventory,
            'knowledge': self.framework / 'knowledge/answers.json',
            'output': self.output,
            'cache': self.framework / '.migration/cache',
            'agent_artifacts': self.framework / 'agent_artifacts',
        }.items():
            self.config_data[key] = os.path.relpath(path, self.config.parent)
        self.config_data.pop('sheet', None)
        self.config_data.pop('target_file', None)  # Exercise shipped target.json.
        write_json(self.config, self.config_data)
        self.unrelated.mkdir()
        venv.EnvBuilder(with_pip=False).create(self.workspace / 'approved Python')

    def set_paths(self):
        self.framework = self.workspace / 'mainframe_migration'
        self.source = self.workspace / 'mainframe source'
        self.inventory = self.workspace / 'process inputs/accounts flow.md'
        self.config = self.framework / 'processes/SYNTHETIC/process.json'
        self.output = self.framework / 'local deliverables'
        self.unrelated = self.workspace / 'unrelated working directory'
        self.python = self.workspace / 'approved Python' / (
            'Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def cli(self, *arguments, cwd=None, expected_code=0):
        cwd = cwd or self.unrelated
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
        environment['PYTHONNOUSERSITE'] = '1'
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        environment['PATH'] = str(self.python.parent)
        completed = subprocess.run(
            [str(self.python), '-S', '-B', str(self.framework / 'modernize.py'),
             *map(str, arguments)], cwd=cwd, env=environment, text=True,
            encoding='utf-8', errors='replace', capture_output=True, timeout=60,
        )
        self.assertEqual(completed.returncode, expected_code,
                         completed.stdout + '\n' + completed.stderr)
        self.assertNotIn('Traceback (most recent call last)', completed.stderr)
        return completed

    def run_process(self, expected_code=0, cwd=None):
        cwd = cwd or self.unrelated
        completed = self.cli('run', '--config', os.path.relpath(self.config, cwd),
                             cwd=cwd, expected_code=expected_code)
        result = read_json(self.output / self.config_data['process'] / 'latest_result.json')
        self.assertIn('STATUS: ' + result['status'], completed.stdout)
        return result

    def assert_outputs(self, result):
        self.assertEqual(result['status'], 'SYNTHETIC_TARGET_VALIDATED', result['issues'])
        self.assertEqual((result['target']['language'], result['target']['database']),
                         ('python', 'sqlite'))
        self.assertEqual(result['metrics']['generated_job_files'], 5)
        self.assertEqual(result['metrics']['steps'], 6)
        verification = result['verification']
        self.assertEqual(verification['native_database'], 'PASSED')
        self.assertEqual(verification['compilation'], 'PASSED')
        self.assertEqual(sum(c['file_passed'] for c in verification['cases']), 18)
        self.assertEqual(sum(c['database_passed'] for c in verification['cases']), 3)
        self.assertEqual(sum(c['rc_passed'] for c in verification['cases']), 15)
        artifact = Path(result['artifact_folder'])
        self.assertEqual({p.name for p in (artifact / 'jobs').glob('*.py')},
                         {name + '.py' for name in self.config_data['execution_order']})
        self.assertTrue((artifact / 'artifact-manifest.json').is_file())
        self.assertTrue((artifact / 'database/logical_schema.json').is_file())
        self.assertTrue((artifact / 'database/schema.sql').is_file())
        run = Path(result['run_folder'])
        for filename in ('process_flow.json', 'discovery.json', 'result.json',
                         'modernization_report.html', 'verification/verification.json'):
            self.assertTrue((run / filename).is_file(), filename)
        self.assertTrue((self.output / self.config_data['process'] /
                         'modernization_report.html').is_file())
        for case in self.config_data['cases']:
            baseline = self.config.parent / case['path']
            work = run / 'verification/cases' / case['name']
            for dataset, expected in case['expected_files'].items():
                destination = work / self.config_data['datasets'][dataset]['path']
                self.assertEqual(destination.read_bytes(), (baseline / expected).read_bytes(),
                                 str(destination))
            with closing(sqlite3.connect(work / 'local.sqlite')) as connection:
                for table, expected in read_json(baseline / case['expected_database']).items():
                    query = 'SELECT ' + ','.join('"' + col + '"' for col in expected['columns'])
                    query += ' FROM "' + table + '"'
                    actual = Counter(tuple(row) for row in connection.execute(query))
                    self.assertEqual(actual, Counter(tuple(row) for row in expected['rows']))
            for job in self.config_data['execution_order']:
                outcome = read_json(work / (job + '-execution.json'))
                self.assertEqual(outcome['exit_code'], 0)
                self.assertTrue((work / (job + '-result.json')).is_file())

    def test_sibling_layout_runs_without_packages_then_reuses_and_relocates(self):
        probe = subprocess.run(
            [str(self.python), '-S', '-c',
             'import sys, sqlite3; assert "site" not in sys.modules; print(sqlite3.sqlite_version)'],
            check=True, text=True, capture_output=True, timeout=30)
        self.assertTrue(probe.stdout.strip())
        no_packages = subprocess.run(
            [str(self.python), '-c',
             'import importlib.util; assert importlib.util.find_spec("pip") is None'],
            check=True, capture_output=True, timeout=30,
            env={**os.environ, 'PYTHONNOUSERSITE': '1', 'PYTHONPATH': ''})
        self.assertEqual(no_packages.returncode, 0)
        source_before = hashes(self.source)
        baselines_before = hashes(self.config.parent / 'cases')
        manifest_before = (self.config.parent / 'baseline_manifest.json').read_bytes()
        first = self.run_process()
        self.assert_outputs(first)
        first_run_before = hashes(Path(first['run_folder']))
        second = self.run_process(cwd=self.framework)
        self.assert_outputs(second)
        self.assertEqual(second['metrics']['models_reused'], 5)
        self.assertEqual(second['metrics']['job_files_reused'], 5)
        self.assertEqual(second['metrics']['job_files_created'], 0)
        self.assertTrue(second['metrics']['target_artifact_reused'])
        self.assertEqual(first['artifact_id'], second['artifact_id'])
        self.assertNotEqual(first['run_folder'], second['run_folder'])
        self.assertEqual(hashes(Path(first['run_folder'])), first_run_before)

        # Operators can move the entire common parent before their next run.
        # Historical logs remain records of the original location.
        moved = self.workspace.with_name('Relocated common parent with spaces')
        self.workspace.rename(moved)
        self.workspace = moved
        self.set_paths()
        relocated = self.run_process()
        self.assert_outputs(relocated)
        self.assertEqual(relocated['metrics']['models_reused'], 5)
        self.assertEqual(relocated['metrics']['job_files_reused'], 5)
        self.assertEqual(relocated['artifact_id'], second['artifact_id'])
        self.assertTrue(Path(relocated['run_folder']).is_relative_to(moved))
        self.assertEqual(hashes(self.source), source_before)
        self.assertEqual(hashes(self.config.parent / 'cases'), baselines_before)
        self.assertEqual((self.config.parent / 'baseline_manifest.json').read_bytes(), manifest_before)

    def test_init_accepts_relative_sibling_paths_and_reports_real_process_gaps(self):
        initial_config = self.framework / 'processes/REAL_PROCESS/process.json'
        initial_config.parent.mkdir()
        completed = self.cli(
            'init', '--repository', os.path.relpath(self.source, self.unrelated),
            '--inventory', os.path.relpath(self.inventory, self.unrelated),
            '--process', 'REAL_PROCESS', '--config', os.path.relpath(initial_config, self.unrelated),
            '--output', os.path.relpath(self.output, self.unrelated),
            '--source-format', 'free', expected_code=2,
        )
        self.assertIn('STATUS: BLOCKED', completed.stdout)
        saved = read_json(initial_config)
        self.assertEqual(saved['generation_mode'], 'agent')
        self.assertEqual(saved['baseline']['kind'], 'mainframe')
        self.assertEqual(saved['cases'], [])
        self.assertNotIn('sheet', saved)
        self.assertEqual(saved['repository'], str(self.source.resolve()))
        self.assertEqual(saved['inventory'], str(self.inventory.resolve()))
        self.assertEqual(saved['output'], str(self.output.resolve()))
        result = read_json(self.output / 'REAL_PROCESS/latest_result.json')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual((result['target']['language'], result['target']['database']), ('python', 'sqlite'))
        self.assertEqual(result['metrics']['jobs_discovered'], 5)
        self.assertIn('AGENT_REQUIRED', {issue['code'] for issue in result['issues']})
        self.assertIn('DATASET_BINDING', {issue['code'] for issue in result['issues']})
        self.assertTrue((Path(result['run_folder']) / 'agent_request.json').is_file())
        self.assertNotIn('artifact_folder', result)

    def test_bad_operator_inputs_block_clearly_without_generating_a_partial_process(self):
        original_md = self.inventory.read_bytes()
        missing_member = self.source / 'cobol/CLASSIFY.cbl'
        original_member = missing_member.read_bytes()
        original_config = self.config.read_bytes()
        cases_before = hashes(self.config.parent / 'cases')
        faults = (
            ('missing Markdown', lambda: self.inventory.unlink(), 'INVENTORY'),
            ('malformed Markdown', lambda: self.inventory.write_text(
                '# Job: JOB001\n| Step | Program |\n| --- | --- |\n| S010 |\n',
                encoding='utf-8'), 'INVENTORY'),
            ('missing source member', lambda: missing_member.unlink(), 'MISSING_MEMBER'),
            ('missing destination', lambda: write_json(self.config, {
                **self.config_data, 'datasets': {k: v for k, v in self.config_data['datasets'].items()
                                                if k != 'SAMPLE.TOTAL'}}), 'DATASET_BINDING'),
        )
        for name, inject, issue_code in faults:
            with self.subTest(name=name):
                self.inventory.write_bytes(original_md)
                missing_member.write_bytes(original_member)
                self.config.write_bytes(original_config)
                inject()
                injected_source = hashes(self.source)
                injected_config = self.config.read_bytes()
                injected_inventory = self.inventory.read_bytes() if self.inventory.exists() else None
                result = self.run_process(expected_code=2)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertIn(issue_code, {issue['code'] for issue in result['issues']}, result)
                self.assertEqual(result['verification']['generation'], 'NOT_RUN')
                self.assertNotIn('artifact_folder', result)
                self.assertEqual(hashes(self.source), injected_source)
                self.assertEqual(self.config.read_bytes(), injected_config)
                self.assertEqual(self.inventory.read_bytes() if self.inventory.exists() else None,
                                 injected_inventory)
                self.assertEqual(hashes(self.config.parent / 'cases'), cases_before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
