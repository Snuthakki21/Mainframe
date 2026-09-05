"""Path guard shared by generated jobs; this is not an operating-system sandbox."""
from pathlib import Path

def inside(root,relative):
    """Keep declared dataset paths inside the selected case/work folder."""
    root=Path(root).resolve();path=Path(relative)
    if path.is_absolute() or '..' in path.parts or ':' in str(path):raise ValueError('Dataset path leaves its managed directory.')
    result=(root/path).resolve()
    if not result.is_relative_to(root):raise ValueError('Dataset link leaves its managed directory.')
    return result
