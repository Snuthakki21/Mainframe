"""Read Markdown process documentation or a legacy five-column Excel inventory.

Only cell values are accepted. Formulas and ambiguous job/step rows are rejected,
not guessed. A blank Job cell repeats the last job, matching common inventories.
Multiple datasets in Input or Output are separated by semicolons or line breaks.
This reader handles ordinary .xlsx workbooks, shared strings, and inline strings.
It does not evaluate macros, formulas, external links, or embedded objects.
"""
from __future__ import annotations
from pathlib import Path, PurePosixPath
import re
import zipfile
import xml.etree.ElementTree as ET
from .common import Blocked

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

def _xml(z: zipfile.ZipFile, name: str) -> ET.Element:
    raw = z.read(name)
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise Blocked('The inventory contains XML entities; provide a plain Excel workbook.', 'INVENTORY')
    return ET.fromstring(raw)

def read_inventory(path: Path, sheet: str = 'Process') -> list[dict]:
    """Return the job, step, program, input, and output stated in each inventory row."""
    path = Path(path)
    if path.suffix.lower() in {'.md', '.markdown'}:
        from .markdown_inventory import read_markdown_inventory
        return read_markdown_inventory(path)
    if path.suffix.lower() != '.xlsx':
        raise Blocked('Supply a .md or .markdown process document with Job headings and Step/Program tables, or a legacy .xlsx inventory with Job, Step, Program, Input, Output in columns A–E.', 'INVENTORY', str(path))
    try:
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist()) > 50_000_000:
                raise Blocked('The workbook expands beyond the 50 MB inventory limit.', 'INVENTORY')
            shared = []
            if 'xl/sharedStrings.xml' in z.namelist():
                shared = [''.join(si.itertext()) for si in _xml(z, 'xl/sharedStrings.xml')]
            book = _xml(z, 'xl/workbook.xml')
            selected = [s for s in book.findall('s:sheets/s:sheet', NS) if s.attrib['name'] == sheet]
            if not selected:
                names = [s.attrib['name'] for s in book.findall('s:sheets/s:sheet', NS)]
                raise Blocked(f'Worksheet {sheet!r} is missing. Available sheets: {names}. Set the sheet name in the process configuration.', 'INVENTORY')
            rid = selected[0].attrib['{' + NS['r'] + '}id']
            rels = _xml(z, 'xl/_rels/workbook.xml.rels')
            relationship = next((r for r in rels if r.attrib['Id'] == rid), None)
            if relationship is None or relationship.attrib.get('TargetMode') == 'External':
                raise Blocked('The selected worksheet is not an internal worksheet.', 'INVENTORY')
            target = relationship.attrib['Target']
            target = target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl') / target)
            if '..' in PurePosixPath(target).parts:
                raise Blocked('The workbook has an unsupported worksheet path.', 'INVENTORY')
            values = []
            for row in _xml(z, target).findall('s:sheetData/s:row', NS):
                cells = [''] * 5
                for cell in row.findall('s:c', NS):
                    match = re.fullmatch(r'([A-Z]+)(\d+)', cell.attrib.get('r', ''))
                    if not match: continue
                    col = match.group(1)
                    if col not in 'ABCDE' or len(col) != 1: continue
                    if cell.find('s:f', NS) is not None:
                        raise Blocked(f'Inventory row {row.attrib.get("r")} contains a formula. Supply its agreed value instead.', 'INVENTORY')
                    typ = cell.attrib.get('t')
                    if typ == 'inlineStr':
                        text = ''.join(cell.find('s:is', NS).itertext())
                    else:
                        val = cell.find('s:v', NS)
                        text = '' if val is None else (val.text or '')
                        if typ == 's': text = shared[int(text)]
                    cells[ord(col) - 65] = text.strip()
                if any(cells): values.append((int(row.attrib['r']), cells))
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, StopIteration) as exc:
        raise Blocked(f'The Excel inventory could not be read: {exc}', 'INVENTORY', str(path)) from exc
    if not values: raise Blocked('The selected inventory sheet is empty.', 'INVENTORY')
    expected = ['job', 'step', 'program', 'input', 'output']
    aliases = {'job name':'job', 'step name':'step', 'program name':'program', 'inputs':'input', 'outputs':'output'}
    header = [aliases.get(x.lower(), x.lower()) for x in values[0][1]]
    if header != expected:
        raise Blocked('The first nonempty row must be Job, Step, Program, Input, Output in columns A–E.', 'INVENTORY')
    result, last_job, seen = [], '', set()
    for number, cells in values[1:]:
        job, step, program, inputs, outputs = cells
        job = job or last_job
        if not all((job, step, program)):
            raise Blocked(f'Inventory row {number} needs a Job, Step, and Program. Only Job may repeat through a blank cell.', 'INVENTORY')
        job, step, program = job.upper(), step.upper(), program.upper()
        if not all(re.fullmatch(r'[A-Z@#$][A-Z0-9@#$_-]*', s) for s in (job,step,program)):
            raise Blocked(f'Inventory row {number} contains an unsupported name.', 'INVENTORY')
        if (job, step) in seen:
            raise Blocked(f'{job}/{step} occurs more than once. Combine its input/output names in one row.', 'INVENTORY')
        seen.add((job, step)); last_job = job
        split = lambda text: [s.strip().upper() for s in re.split('[;\n]', text) if s.strip()]
        result.append({'job':job,'step':step,'program':program,'inputs':split(inputs),'outputs':split(outputs),'row':number})
    if not result: raise Blocked('The inventory has no job rows.', 'INVENTORY')
    return result
