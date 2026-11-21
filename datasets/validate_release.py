"""Read-only checks of the English-localized release. No semantic re-adjudication."""
from pathlib import Path
import hashlib, json, importlib.util, sys, copy
sys.dont_write_bytecode=True
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(r):return hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
    checks=read(ROOT/'release_checksums.json')
    for rel,want in checks.items():
        assert digest(ROOT/rel)==want, f'Packaged file changed: {rel}'
    schema=Draft202012Validator(read(ROOT/'schema/data_truth_schema.json'))
    summary={}
    for label,rel,mod,count in [('2wiki','final/2wiki/2wiki_audit_gold.jsonl','convert_2wiki_final_silver_to_schema_3',400),('musique','final/musique/musique_final_gold_167_schema3_core.jsonl','convert_musique_final_200_to_schema_3',167)]:
        spec=importlib.util.spec_from_file_location(mod,ROOT/'adapters/schema3'/f'{mod}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        data=rows(ROOT/rel)
        assert len(data)==count and len({r['sample']['sample_id'] for r in data})==count
        for r in data:schema.validate(r);m.validate_relations(r)
        summary[label]={'records':len(data),'claims':sum(len(r['claims']) for r in data),'links':sum(len(r['claim_source_links']) for r in data),'schema_and_frozen_relational_checks':'passed'}
    core=rows(ROOT/'final/musique/musique_final_gold_167_schema3_core.jsonl'); side=rows(ROOT/'final/musique/musique_final_gold_167_schema3_sidecar.jsonl');extended=rows(ROOT/'final/musique/musique_final_gold_167.jsonl')
    assert len(core)==len(side)==len(extended)==167
    for c,s,e in zip(core,side,extended):
        assert c['sample']['sample_id']==s['sample_id']==e['sample']['sample_id']
        assert canon(c)==s['core_record_sha256']
        r=copy.deepcopy(c);r['sample']['normalization_status']=s['normalization_status_projection']['extended_value'];r['human_audit']=copy.deepcopy(s['human_audit'])
        by={}
        for x in s['sentence_level_evidence']['document_sentences']:
            y=copy.deepcopy(x);context=y.pop('context_id');by.setdefault(context,[]).append(y)
        for d in r['documents']:d['sentences']=by.get(d['context_id'],[])
        links={x['claim_id']:x for x in s['sentence_level_evidence']['claim_source_links']}
        for link in r['claim_source_links']:link['supporting_sentences']=copy.deepcopy(links[link['claim_id']]['supporting_sentences'])
        assert r==e, 'Sidecar reconstruction differs'
    summary['sidecar_lossless_reconstruction']='passed';summary['packaged_file_hashes_checked']=len(checks)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
