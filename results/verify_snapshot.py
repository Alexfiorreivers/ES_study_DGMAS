"""Read-only verification of the English publication snapshot (stdlib only)."""
from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parent
def rows(path):
    with path.open(encoding='utf-8-sig') as f:return [json.loads(s) for s in f if s.strip()]
def main():
    manifest=json.loads((ROOT/'FILES.sha256.json').read_text(encoding='utf-8'))
    bad=[]
    for name,sha in manifest.items():
        p=ROOT/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:bad.append(name)
    assert not bad, {'hash_mismatches':bad}
    stage=ROOT/'research_change/final_statistics_stage_20261012'
    terminal=rows(stage/'terminal_union_statistics_20261015/terminal_analysis_ledger.jsonl')
    node=rows(stage/'paper_node_edge_statistics_20261013/node_analysis_ledger.jsonl')
    edge=rows(stage/'paper_node_edge_statistics_20261013/edge_analysis_ledger.jsonl')
    assert len(terminal)==1366 and len(node)==7098 and len(edge)==2444
    assert len({r['scope_id'] for r in terminal})==1366
    assert sum(r['judgment'] is None for r in terminal)==1036
    assert sum(r['sampled'] for r in terminal)==120
    assert sum(r['route']!='simple_proxy_population' for r in terminal)==210
    assert len({r['observation_key'] for r in terminal})==520
    assert len({r['question_id'] for r in terminal})==60
    for items,known,sample,unknown,primary in [(node,769,633,5696,4898),(edge,559,189,1696,1444)]:
        assert sum(r['exact_judgment'] is not None for r in items)==known
        assert sum(r['sample_analysis_judgment'] is not None for r in items)==sample
        assert sum(r['exact_judgment'] is None and r['sample_analysis_judgment'] is None for r in items)==unknown
        selected=[r for r in items if r['model']=='DeepSeek/deepseek-flash' and r['prompt_ref'].endswith('@1.0.4') and r['observation_version']=='original_protocol']
        assert len(selected)==primary
    final=json.loads((stage/'terminal_union_primary_20261013/FINALIZATION_STATUS_20261015.json').read_text(encoding='utf-8-sig'))
    print(json.dumps({'status':'PASS','publication_files_checked':len(manifest),'node_scopes':len(node),'edge_scopes':len(edge),'terminal_scopes':len(terminal),'primary_node_scopes':4898,'primary_edge_scopes':1444,'terminal_unreviewed':1036,'question_count':60,'terminal_runs':520,'note':'Current English-publication hashes and frozen counts only; embedded historical hashes refer to original source bytes. No re-adjudication, resampling, model call or statistical rebuilding.'},indent=2))
if __name__=='__main__':main()
