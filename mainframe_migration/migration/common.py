"""Small shared safeguards.

These helpers keep paths within the selected working area, write files completely,
and give every blocking question a repeatable identifier. They do not run Git,
contact an AI service, or change the application's business rules.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

class Blocked(Exception):
    """Stop the affected activity because proceeding would require a guess."""
    def __init__(self, message: str, code: str = 'UNSUPPORTED_SOURCE', source: str = ''):
        super().__init__(message)
        self.message, self.code, self.source = message, code, source
    def issue(self, job: str = '') -> dict:
        identity = f'{self.code}|{job}|{self.source}|{self.message}'
        return {'id': 'Q-' + hashlib.sha256(identity.encode()).hexdigest()[:10],
                'code': self.code, 'job': job, 'source': self.source,
                'question': self.message, 'owner': 'Migration agent' if self.code == 'AGENT_REQUIRED' else 'Mainframe SME',
                'status': 'open'}

def digest(data: bytes) -> str:
    """Identify the exact bytes, rather than trusting a filename or modified date."""
    return hashlib.sha256(data).hexdigest()

def fingerprint(value: Any) -> str:
    """Give equivalent structured evidence the same identifier."""
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())

def read_json(path: Path) -> Any:
    """Read UTF-8 JSON, including files saved with a Windows byte-order mark."""
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write_json(path: Path, value: Any) -> None:
    """Publish a complete JSON file; an interrupted write does not leave half a file."""
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=True) + '\n')

def atomic_write(path: Path, data: str | bytes) -> None:
    """Write beside the destination, then replace it in one filesystem operation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode('utf-8') if isinstance(data, str) else data
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.writing-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def inside(root: Path, relative: str | Path) -> Path:
    """Reject absolute paths, traversal, and links that lead outside a managed area."""
    root = root.resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):
        raise Blocked(f'Use a relative path inside {root.name}; this path leaves that area: {relative}', 'UNSAFE_PATH')
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise Blocked(f'The path points outside the selected folder: {relative}', 'UNSAFE_PATH')
    return result

def snapshot(paths: list[Path]) -> dict[str, str]:
    """Capture protected source and baseline bytes before executing migrated code."""
    return {str(p.resolve()): digest(p.read_bytes()) for p in paths if p.is_file()}

def changed(before: dict[str, str]) -> list[str]:
    """Find protected files modified or removed during a run; never restore silently."""
    return [name for name, value in before.items()
            if not Path(name).is_file() or digest(Path(name).read_bytes()) != value]
