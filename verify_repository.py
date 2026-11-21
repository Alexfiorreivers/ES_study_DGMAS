"""Read-only verification of the packaging manifest (not statistical replication)."""
from pathlib import Path
import hashlib
import json
import sys


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'REPOSITORY_MANIFEST.json').read_text(encoding='utf-8'))
    failures = []
    for row in manifest['files']:
        path = (root / row['path']).resolve()
        if not path.is_relative_to(root):
            failures.append({'path': row['path'], 'reason': 'outside repository'})
        elif not path.is_file():
            failures.append({'path': row['path'], 'reason': 'missing'})
        elif (path.stat().st_size != row['bytes'] or
              hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            failures.append({'path': row['path'], 'reason': 'changed since packaging'})
    print(json.dumps({'status': 'FAIL' if failures else 'PASS',
                      'files_checked': len(manifest['files']), 'failures': failures,
                      'note': 'Extra files are not checked. Regenerating outputs can change their hashes.'},
                     ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
