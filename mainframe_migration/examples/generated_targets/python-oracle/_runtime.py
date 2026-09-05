"""Runtime used by generated job files.

It reads fixed-length records locally, stores money as exact decimal values,
preserves text width, and delegates database work to the selected adapter. No AI sees or
processes each business record. These helpers implement the documented offline
subset, not every IBM COBOL data representation or DB2 transaction behavior.
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal, ROUND_DOWN, localcontext
from pathlib import Path
from typing import Any
from _common import inside
from _database import Database

class Fields:
    """Keep group records and their individual fields in the same fixed-width storage.

    For unsigned DISPLAY numbers, assignment truncates fractional digits and keeps
    the low-order digits on overflow. Unsupported signed/packed/binary layouts are
    rejected by the compiler instead of pretending this representation covers them.
    """
    def __init__(self, layout: list[dict]):
        self.layout = {item['name']:item for item in layout}
        self.buffers: dict[str,list[str]] = {}
        self.aliases: dict[str,tuple[Fields,str]] = {}
        for item in layout:
            size = item['offset'] + item['length']
            current = self.buffers.setdefault(item['root'],[])
            if len(current) < size: current.extend(' ' * (size-len(current)))
        for item in layout:
            if item['kind'] == 'number': self.set(item['name'],Decimal(0))
        for item in layout:
            if 'value' in item: self.set(item['name'],item['value'])
    def raw(self, name: str) -> str:
        """Return the exact record characters, including zeros and trailing spaces."""
        item = self.layout[name]
        storage, start = self._storage(name)
        return ''.join(storage[start:start+item['length']])
    def get(self, name: str) -> Decimal | str:
        """Interpret a numeric field only when its declared picture says it is numeric."""
        item, text = self.layout[name], self.raw(name)
        if item['kind'] != 'number': return text
        if not text or not all('0' <= c <= '9' for c in text):
            raise ValueError(f'{name} has nonnumeric data in a numeric field; it cannot be silently changed to zero.')
        return Decimal(text).scaleb(-item['scale'])
    def set(self, name: str, value: Any) -> None:
        """Apply the receiving field's width and scale, not Python's default formatting."""
        item = self.layout[name]
        if item['kind'] == 'number':
            if isinstance(value,float): raise TypeError('Binary floats are not allowed for exact numeric fields.')
            with localcontext() as dc:
                dc.prec = 80
                number = Decimal(value)
                if not number.is_finite(): raise ValueError('Non-finite decimal values are not valid COBOL numeric data.')
                scaled = abs(number).scaleb(item['scale']).to_integral_value(rounding=ROUND_DOWN)
                text = str(int(scaled) % (10 ** item['length'])).zfill(item['length'])
        else:
            text = str(value)[:item['length']].ljust(item['length'])
        storage, start = self._storage(name)
        storage[start:start+item['length']] = list(text)
    def _storage(self, name: str) -> tuple[list[str],int]:
        """Locate the underlying record, including a live CALL BY REFERENCE alias."""
        item = self.layout[name]
        if item['root'] in self.aliases:
            owner, original = self.aliases[item['root']]
            storage, base = owner._storage(original)
            return storage, base + item['offset']
        return self.buffers[item['root']], item['offset']
    def reference(self, name: str) -> tuple[Fields,str]:
        """Pass a storage address without interpreting an output-only numeric field."""
        if name not in self.layout: raise KeyError(name)
        return self, name
    def bind(self, name: str, reference: tuple[Fields,str]) -> None:
        """Make a linkage field share the caller's bytes, including repeated aliases."""
        owner, original = reference
        item = self.layout[name]
        if item['root'] != name or item['offset'] != 0:
            raise ValueError('Offline linkage arguments must be level-01 fields.')
        if owner.length(original) != self.length(name):
            raise ValueError('CALL linkage lengths differ; source-specific review is required.')
        self.aliases[name] = (owner, original)
    def length(self, name: str) -> int:
        """Return the source picture width in single-byte record characters."""
        return self.layout[name]['length']

def relation(left: Any, op: str, right: Any, encoding: str) -> bool:
    """Compare numbers numerically and text in the explicitly selected code page."""
    if isinstance(left,str) and isinstance(right,str):
        size = max(len(left),len(right))
        left, right = left.ljust(size).encode(encoding), right.ljust(size).encode(encoding)
    operations = {'=':lambda:left==right,'<>':lambda:left!=right,
                  '>':lambda:left>right,'<':lambda:left<right,
                  '>=':lambda:left>=right,'<=':lambda:left<=right}
    return operations[op]()

class RecordFile:
    """Stream fixed records without line-ending conversion or stripping spaces."""
    def __init__(self, path: Path, mode: str, encoding: str, length: int):
        self.path, self.encoding, self.length = path, encoding, length
        if mode == 'OUTPUT': path.parent.mkdir(parents=True,exist_ok=True)
        self.handle = path.open('rb' if mode == 'INPUT' else 'wb')
    def read(self) -> str | None:
        raw = self.handle.read(self.length)
        if not raw: return None
        if len(raw) != self.length:
            raise ValueError(f'{self.path.name} ends with a partial record: {len(raw)} bytes; expected {self.length}.')
        text = raw.decode(self.encoding, errors='strict')
        if len(text) != self.length:
            raise ValueError('Only single-byte encodings are supported by fixed-record layouts.')
        return text
    def write(self, text: str) -> None:
        raw = text.encode(self.encoding,errors='strict')
        if len(raw) != self.length:
            raise ValueError(f'{self.path.name}: the program wrote {len(raw)} bytes; expected {self.length}.')
        self.handle.write(raw)
    def close(self) -> None:
        self.handle.close()

class Context:
    """Give one job explicit file and database access within its local test run.

    Path checks reduce accidental writes outside the work area. They are not an OS
    security sandbox for arbitrary agent-authored Python. Run approved generated
    code only; the framework does not claim Python can sandbox arbitrary Python.
    """
    def __init__(self, payload: dict):
        self.payload = payload
        self.case_root, self.work_root = Path(payload['case_root']), Path(payload['work_root'])
        self.datasets, self.schema = payload['datasets'], payload.get('schema',{})
        self.encoding = payload.get('collation','cp037')
        self.events: Counter[str] = Counter()
        self.opened: list[RecordFile] = []
        self.db = Database(payload)
    def hit(self, source_id: str) -> None:
        """Record which translated statement actually ran; unvisited branches stay visible."""
        self.events[source_id] += 1
    def dataset(self, dd: dict) -> tuple[Path,dict]:
        if 'dsn' not in dd: raise ValueError('This program needs a concrete dataset binding for its DD.')
        spec = self.datasets[dd['dsn']]
        root = self.case_root if spec['role'] == 'input' else self.work_root
        return inside(root,spec['path']), spec
    def open(self, dd: dict, mode: str, record_length: int) -> RecordFile:
        """Check the declared layout before opening the dataset."""
        path, spec = self.dataset(dd)
        if spec['format'] != 'fixed': raise ValueError('Only fixed record files are enabled in the offline runtime.')
        if mode == 'OUTPUT' and spec['role'] == 'input':
            raise ValueError('A job tried to overwrite a protected input dataset.')
        if int(spec['record_length']) != record_length:
            raise ValueError(f'{dd["dsn"]}: COBOL length {record_length} differs from dataset length {spec["record_length"]}.')
        stream = RecordFile(path,mode,spec['encoding'],record_length)
        self.opened.append(stream)
        return stream
    def copy(self, source: dict, target: dict) -> None:
        """Reproduce a record-for-record copy; no filtering, trimming, or deduplication."""
        _, spec = self.dataset(source)
        read = self.open(source,'INPUT',int(spec['record_length']))
        write = self.open(target,'OUTPUT',int(spec['record_length']))
        while True:
            record = read.read()
            if record is None: break
            write.write(record)
        read.close(); write.close()
    def sort(self, source: dict, target: dict, keys: list[list], max_records: int = 100000) -> None:
        """Keep duplicates and original tie order; stop rather than overrun the memory limit."""
        _, spec = self.dataset(source)
        read = self.open(source,'INPUT',int(spec['record_length']))
        rows = []
        while True:
            record = read.read()
            if record is None: break
            rows.append(record)
            if len(rows) > max_records: raise ValueError('Sort exceeds the configured local record limit; an external sort is required.')
        read.close()
        for start, length, typ, direction in reversed(keys):
            def key(row, start=start, length=length, typ=typ):
                token = row[start-1:start-1+length]
                if len(token) != length: raise ValueError('Sort key extends beyond the record.')
                if typ == 'CH': return token.encode(spec['encoding'])
                if not token.isascii() or not token.isdigit():
                    raise ValueError('The supported unsigned ZD key contains non-digit data.')
                return Decimal(token)
            rows.sort(key=key,reverse=direction=='D')
        write = self.open(target,'OUTPUT',int(spec['record_length']))
        for record in rows: write.write(record)
        write.close()
    def insert(self, table, columns, values):
        """Write source values using the selected database implementation."""
        self.db.insert(table, columns, values)
    def commit(self):
        """Commit only because the source requests it."""
        self.db.commit()
    def rollback(self):
        """Retain the source rollback boundary."""
        self.db.rollback()
    def end_step(self):
        """Close step files without carrying pending writes into another step."""
        self.finish()
        for stream in self.opened:
            if not stream.handle.closed: stream.close()
        self.opened.clear()
    def finish(self):
        """Reject a missing source transaction decision rather than choosing one."""
        self.db.finish()
    def close(self):
        """Close files and the owned database connection even after a job failure."""
        for stream in self.opened:
            if not stream.handle.closed: stream.close()
        self.db.close()
