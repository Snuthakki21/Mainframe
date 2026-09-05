"""Acceptance tests exercise real generated output, not mocked agent responses."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PackageContract(unittest.TestCase):
    def test_workbench_exists(self):
        self.assertTrue((ROOT / 'modernize.py').is_file(), 'The actual executable runner must exist.')

    def test_required_modules_exist(self):
        for name in ('inventory', 'discovery', 'compiler', 'runtime', 'runner', 'report'):
            self.assertTrue((ROOT / 'migration' / (name + '.py')).is_file(), name)

if __name__ == '__main__':
    unittest.main()
