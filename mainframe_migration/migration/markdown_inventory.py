"""Read the documented process scope without treating prose as executable evidence.

Job headings scope ordinary Markdown pipe tables. Step and Program are required;
Input, Output and Description may vary between sections. Missing I/O columns and
explicitly empty I/O cells remain distinguishable through ``fields_present``.
Source line numbers point to original physical rows, never reformatted Markdown.
"""
from __future__ import annotations

from pathlib import Path
import re

from .common import Blocked


_HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.+?)\s*$')
_FENCE = re.compile(r'^\s{0,3}(`{3,}|~{3,})(.*)$')
_MEMBER = re.compile(r'[A-Z@#$][A-Z0-9@#$_-]*')
_SEPARATOR = re.compile(r':?-{3,}:?')
_ALIASES = {'job name': 'job', 'step name': 'step', 'program name': 'program',
            'inputs': 'input', 'outputs': 'output'}
_FIELDS = {'job', 'step', 'program', 'input', 'output', 'description'}
_EMPTY_DATASETS = {'NONE', 'N/A', '-'}


def _inline(text: str) -> str:
    """Remove simple display markup while keeping identifiers and prose intact."""
    text = text.strip()
    text = re.sub(r'(`+)(.+?)\1', r'\2', text)
    for pattern in (r'(?<!\w)(\*\*|__)(?=\S)(.+?)(?<=\S)\1(?!\w)',
                    r'(?<!\w)(\*|_)(?=\S)(.+?)(?<=\S)\1(?!\w)'):
        text = re.sub(pattern, r'\2', text)
    return re.sub(r'\\([\\`*_{}\[\]()#+.!|>\-])', r'\1', text).strip()


def _cells(line: str) -> list[str] | None:
    """Split real table delimiters, respecting escaped and inline-code pipes."""
    line = line.strip()
    cells, current, delimiters = [], [], []
    code_width = 0
    i = 0
    while i < len(line):
        char = line[i]
        if char == '\\' and i + 1 < len(line):
            # Preserve escapes for inline cleanup; an escaped pipe is not a cell.
            current.extend((char, line[i + 1]))
            i += 2
            continue
        if char == '`':
            end = i + 1
            while end < len(line) and line[end] == '`':
                end += 1
            width = end - i
            if not code_width:
                code_width = width
            elif code_width == width:
                code_width = 0
            current.append(line[i:end])
            i = end
            continue
        if char == '|' and not code_width:
            cells.append(''.join(current).strip())
            current = []
            delimiters.append(i)
        else:
            current.append(char)
        i += 1
    if not delimiters:
        return None
    cells.append(''.join(current).strip())
    if delimiters[0] == 0:
        cells.pop(0)
    if delimiters[-1] == len(line) - 1:
        cells.pop()
    return cells


def _header(text: str) -> str:
    value = ' '.join(_inline(text).lower().split())
    return _ALIASES.get(value, value)


def _datasets(text: str) -> list[str]:
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    values = [_inline(value).upper() for value in re.split(r'[;\n]', text)]
    return [value for value in values if value and value not in _EMPTY_DATASETS]


def read_markdown_inventory(path: Path) -> list[dict]:
    """Return every documented row, or stop with its source line if ambiguous."""
    def fail(message: str, line: int) -> None:
        raise Blocked(f'Markdown inventory line {line}: {message}', 'INVENTORY', f'{path}:{line}')

    try:
        if path.stat().st_size > 50_000_000:
            fail('The document exceeds the 50 MB inventory limit.', 1)
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except (OSError, UnicodeError) as exc:
        raise Blocked(f'The Markdown inventory could not be read as UTF-8: {exc}',
                      'INVENTORY', str(path)) from exc

    rows, seen = [], set()
    job, job_level, section = '', 0, ''
    job_declaration = None
    last_headers = ['step', 'program']
    fence = None
    first_table = None
    i = 0
    while i < len(lines):
        line = lines[i]
        fence_match = _FENCE.match(line)
        if fence is not None:
            if (fence_match and fence_match[1][0] == fence[0]
                    and len(fence_match[1]) >= fence[1] and not fence_match[2].strip()):
                fence = None
            i += 1
            continue
        if fence_match:
            fence = (fence_match[1][0], len(fence_match[1]))
            i += 1
            continue
        heading = _HEADING.match(line)
        if heading:
            # ATX closing hashes require preceding whitespace. JOB# is a member.
            label = _inline(re.sub(r'\s+#+\s*$', '', heading[2]))
            job_heading = re.match(r'^job(?:\s+name)?\s*:\s*(.*)$', label, re.I)
            if job_declaration and (job_heading or len(heading[1]) <= job_level):
                if len(rows) == job_declaration[2]:
                    fail(f'Job {job_declaration[0]} has no process rows. Supply its Step/Program table.', job_declaration[1])
                job_declaration = None
            if job_heading:
                job = _inline(job_heading[1]).upper()
                if not _MEMBER.fullmatch(job):
                    fail('The Job heading needs one supported job name after "Job:".', i + 1)
                job_level, section = len(heading[1]), ''
                job_declaration = (job, i + 1, len(rows))
                last_headers = ['step', 'program']
            elif job and len(heading[1]) > job_level:
                section = label
            else:
                job, job_level, section = '', 0, ''
            i += 1
            continue
        header_cells = _cells(line)
        if header_cells is None:
            i += 1
            continue
        headers = [_header(cell) for cell in header_cells]
        candidate = bool({'job', 'step', 'program'}.intersection(headers))
        separator = _cells(lines[i + 1]) if i + 1 < len(lines) else None
        has_separator = bool(separator) and all(_SEPARATOR.fullmatch(cell) for cell in separator)
        if not has_separator:
            if candidate:
                fail('A process table header needs a Markdown separator row such as | --- | --- |.', i + 1)
            if job or first_table is not None:
                fail('An orphan table row appears outside a process table. Repeat its Step/Program '
                     'header and separator after blank lines or prose.', i + 1)
            i += 1
            continue
        if not candidate:
            required_positions = [last_headers.index(name) for name in ('step', 'program')]
            if ((job or first_table is not None)
                    and any(position < len(header_cells)
                            and _MEMBER.fullmatch(_inline(header_cells[position]).upper())
                            for position in required_positions)):
                fail('An orphan row or unrecognized process table could hide a step. '
                     'Supply explicit Step and Program column headers.', i + 1)
            # Skip unrelated tables as a unit; their values are not new headers.
            i += 2
            while i < len(lines) and not _HEADING.match(lines[i]) and _cells(lines[i]) is not None:
                i += 1
            continue
        first_table = first_table or i + 1
        if len(separator) != len(headers):
            fail(f'The separator must have {len(headers)} cells to match the header.', i + 2)
        if not all(headers) or len(headers) != len(set(headers)):
            fail('The process table has a blank or duplicate column name.', i + 1)
        if not {'step', 'program'}.issubset(headers):
            fail('Each process table must contain Step and Program columns.', i + 1)
        last_headers = headers
        table_job = job
        i += 2
        while i < len(lines) and not _HEADING.match(lines[i]):
            cells = _cells(lines[i])
            if cells is None:
                break
            if len(cells) != len(headers):
                fail(f'The row needs {len(headers)} cells to match its header; found {len(cells)}. '
                     'Keep each row on one physical line and use <br> inside cells.', i + 1)
            values = dict(zip(headers, cells))
            explicit_job = _inline(values.get('job', '')).upper()
            if job and explicit_job and explicit_job != job:
                fail(f'Job {explicit_job} differs from the current Job heading {job}.', i + 1)
            row_job = explicit_job or table_job
            step = _inline(values.get('step', '')).upper()
            program = _inline(values.get('program', '')).upper()
            if not all((row_job, step, program)):
                fail('Each row needs a Job, Step, and Program. Supply a Job heading or Job column; '
                     'only Job may repeat through a blank cell.', i + 1)
            if not all(_MEMBER.fullmatch(name) for name in (row_job, step, program)):
                fail('The row contains an unsupported Job, Step, or Program name.', i + 1)
            if (row_job, step) in seen:
                fail(f'{row_job}/{step} occurs more than once. Combine its input/output names in one row.', i + 1)
            inputs = _datasets(values.get('input', ''))
            outputs = _datasets(values.get('output', ''))
            row = {'job': row_job, 'step': step, 'program': program,
                   'inputs': inputs, 'outputs': outputs, 'row': i + 1,
                   'source': str(path), 'section': section,
                   'description': _inline(values.get('description', '')),
                   'fields_present': headers.copy(),
                   'documentation_only': program == 'NONE' and not inputs and not outputs}
            extras = {name: _inline(value) for name, value in values.items() if name not in _FIELDS}
            if extras:
                row['extra_fields'] = extras
            rows.append(row)
            seen.add((row_job, step))
            table_job = row_job
            i += 1
    if job_declaration and len(rows) == job_declaration[2]:
        fail(f'Job {job_declaration[0]} has no process rows. Supply its Step/Program table.', job_declaration[1])
    if first_table is None:
        fail('The document has no recognized process tables. Supply Job headings and tables with Step and Program columns.', 1)
    if not rows:
        fail('The document has no job rows beneath its process table headers.', first_table)
    return rows
