"""Delete only this app's diagnostic screenshots; never recurse or follow links."""
from pathlib import Path
import re


def clear_run_screenshots(root):
    directory = Path(root) / 'logs'
    if directory.is_symlink():
        raise ValueError('截圖目錄是連結，未刪除任何檔案')
    count = size = 0
    failures = []
    if not directory.exists():
        return count, size, failures
    for path in directory.iterdir():
        if not re.fullmatch(r'\d{8}-\d{6}-\d{6}-(error|stopped|noorder-\d+)\.png', path.name):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        try:
            length = path.stat().st_size
            path.unlink()
            count += 1
            size += length
        except FileNotFoundError:
            pass
        except OSError as exc:
            failures.append(f'{path.name}: {exc}')
    return count, size, failures
