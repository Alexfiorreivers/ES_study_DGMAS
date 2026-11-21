"""Read-only verification of original archive members; no statistical evaluation."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json

def main():
 root=Path(__file__).resolve().parent
 pairs=[('original_records/deepseek_original_checkpoints.zip','original_records/deepseek_manifest.json'),('original_records/original_inputs_and_annotations.zip','original_records/inputs_annotations_manifest.json'),('original_qwen_chain/qwen_chain_original_records.zip','original_qwen_chain/manifest.json')]
 reports=[]
 for archive,manifest in pairs:
  data=json.loads((root/manifest).read_text(encoding='utf-8'));rows=data['files']
  with ZipFile(root/archive) as z:
   assert set(z.namelist())=={r['archive_path'] for r in rows},archive
   for row in rows:
    raw=z.read(row['archive_path'])
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['archive_path']
  reports.append({'archive':archive,'members':len(rows),'unavailable':len(data.get('unavailable',[]))})
 print(json.dumps({'status':'PASS','archives':reports,'record_level_recomputation':False},indent=2))

if __name__=='__main__':main()
