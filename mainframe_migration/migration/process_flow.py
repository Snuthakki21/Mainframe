"""Normalize supplied process documentation without deriving executable behavior.

Markdown selects and describes the process. JCL and member sources remain the
execution authority; local destinations are copied only from process bindings.
"""
from __future__ import annotations
from pathlib import Path
from .common import digest


def documentation_only(row: dict) -> bool:
    """Recognize an explicit no-program marker only when it has no dataset work."""
    return (row.get('program', '').upper() == 'NONE'
            and not row.get('inputs') and not row.get('outputs'))


def normalize_flow(rows: list[dict], cfg: dict, inventory: Path, discovery: dict | None = None) -> dict:
    """Retain row provenance and explicit bindings, including unresolved destinations."""
    normalized = []
    bindings = {}
    database_objects = {}

    def binding(name):
        if name not in bindings:
            spec = cfg.get('datasets', {}).get(name)
            bindings[name] = {
                'dataset': name,
                'path': spec.get('path') if spec else None,
                'configured_role': spec.get('role') if spec else None,
                'destination_status': 'CONFIGURED' if spec and spec.get('path') else 'UNRESOLVED',
                'documented_inputs': [], 'documented_outputs': [], 'jcl_references': [],
            }
        return bindings[name]

    for source_row in rows:
        row = dict(source_row)
        row.setdefault('source', str(inventory))
        row.setdefault('section', '')
        row.setdefault('description', '')
        row.setdefault('fields_present', ['job', 'step', 'program', 'input', 'output'])
        row['documentation_only'] = documentation_only(row)
        row['kind'] = 'DOCUMENTATION_ONLY' if row['documentation_only'] else 'EXECUTABLE_STEP'
        normalized.append(row)
        reference = {k: row.get(k) for k in ('job', 'step', 'source', 'row', 'section')}
        for field in ('inputs', 'outputs'):
            for name in row.get(field, []):
                if name.startswith('TABLE:'):
                    table = name.removeprefix('TABLE:')
                    obj = database_objects.setdefault(table, {
                        'name': table, 'kind': 'table',
                        'schema_status': 'SOURCE_DDL' if table in (discovery or {}).get('schema', {}) else 'UNRESOLVED',
                        'documented_inputs': [], 'documented_outputs': [],
                    })
                    obj['documented_' + field].append(dict(reference))
                else:
                    binding(name)['documented_' + field].append(dict(reference))

    for job in (discovery or {}).get('jobs', []):
        for step in job['steps']:
            for ddname, dd in step['dds'].items():
                if 'dsn' in dd:
                    binding(dd['dsn'])['jcl_references'].append({
                        'job': job['name'], 'step': step['name'], 'dd': ddname,
                        'source': step['source'], 'line': dd['line'],
                    })
    # Configured outputs remain inspectable even if documentation omits their names.
    for name in cfg.get('datasets', {}):
        binding(name)
    return {
        'schema_version': 1, 'process': cfg['process'],
        'inventory': {'path': str(inventory), 'format': inventory.suffix.lower().lstrip('.'),
                      'sha256': digest(inventory.read_bytes())},
        'documented_job_order': list(dict.fromkeys(row['job'] for row in rows)),
        'execution_order': list(cfg['execution_order']),
        'order_evidence': cfg.get('order_evidence', ''),
        'rows': normalized, 'dataset_bindings': list(bindings.values()),
        'database_objects': list(database_objects.values()),
        'authority': 'Documentation supplies scope and intent. Sources define behavior. '
                     'Dataset paths and roles come only from the process configuration; '
                     'table order does not establish cross-job scheduling.',
    }


def build_process_flow(rows: list[dict], cfg: dict, paths: dict, found: dict | None = None) -> dict:
    """Expose the same documented process contract to both supported runners."""
    return normalize_flow(rows, cfg, paths['inventory'], found)
