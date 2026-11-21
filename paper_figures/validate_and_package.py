"""Read-only CSV validation. Legacy filename: no packaging or output writes."""
from pathlib import Path
import runpy
if __name__=='__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'results/current_release/validate_release_alignment.py'),run_name='__main__')
