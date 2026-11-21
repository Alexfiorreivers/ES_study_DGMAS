"""Verify the exact public file list; no model calls or statistical reconstruction."""
from pathlib import Path
import json,hashlib,sys

ROOT=Path(__file__).resolve().parent
SKIP_DIRS={'.git','__pycache__','.venv','venv','node_modules','.pytest_cache','.mplconfig','generated','outputs','runs','.cache','.test_tmp'}
def main():
    rows=json.loads((ROOT/'REPOSITORY_MANIFEST.json').read_text(encoding='utf-8'))['files']
    expected={x['path'] for x in rows}|{'REPOSITORY_MANIFEST.json'}
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in SKIP_DIRS for x in p.relative_to(ROOT).parts)}
    failures=[]
    if actual!=expected:failures.append({'extra':sorted(actual-expected),'missing':sorted(expected-actual)})
    forbidden=('datasets/final/','results/original_records/','results/original_qwen_chain/','results/verification_additions/')
    for n in actual:
        if n.startswith(forbidden) or Path(n).suffix.lower() in {'.zip','.gz','.bundle'}:failures.append({'withheld_material_or_archive':n})
    for x in rows:
        p=ROOT/x['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']:failures.append({'hash_mismatch':x['path']})
    print(json.dumps({'status':'FAIL' if failures else 'PASS','public_files':len(actual),'failures':failures,'history_warning':'This check excludes .git. Publish only the history-free export; old history contains withheld records.'},indent=2))
    return int(bool(failures))
if __name__=='__main__':sys.exit(main())
