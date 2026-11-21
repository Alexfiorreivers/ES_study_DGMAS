"""Independent read-only arithmetic, denominator, pairing and hash verification."""
from pathlib import Path
import csv,json,hashlib,collections,math
P=Path(__file__).resolve().parent
def rows(n):
    with (P/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-8),(a,b)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
m=json.loads((P/'manifest.json').read_text(encoding='utf-8'))
for p,h in m['input_sha256'].items():assert sha(p)==h,p
for p,h in m['output_sha256'].items():assert sha(P/p)==h,p
c=rows('panel_cells.csv');assert len(c)==11
assert sum(int(r['observation_n']) for r in c)==680
assert sum(int(r['node_scope_n']) for r in c)==7098
assert sum(int(r['edge_scope_n']) for r in c)==2444
g={(r['kind'],r['view'],r['metric']):float(r['estimated_count']) for r in rows('scope_global_metrics.csv')}
for kind,n,ne,ns in [('node',7098,769,633),('edge',2444,559,189)]:
    records=[json.loads(l) for l in (P/(kind+'_analysis_ledger.jsonl')).open(encoding='utf-8')]
    assert len(records)==len({r['scope_id'] for r in records})==n
    assert sum(r['exact_judgment'] is not None for r in records)==ne
    assert sum(r['sample_analysis_judgment'] is not None for r in records)==ns
    totals=collections.Counter();outside=0
    for r in records:
        j=r['exact_judgment'] or r['sample_analysis_judgment']
        if r['original_candidate']:assert r['original_candidate']['is_final'] is False
        if not j:continue
        w=r['expansion_weight'];totals['disposition_'+j['disposition']]+=w
        if kind=='node':
            eq=j['claim_presence']=='present_equivalent'
            totals['CSR']+=w*eq
            totals['ESS']+=w*(j['exact_set_survived'] is True)
            totals['AA']+=w*(eq and j['support_fine']=='fully_supported')
            totals['VSSR']+=w*(j['source_change_status']=='substituted_valid')
        else:
            app=j['claim_event'] in ['claim_retained_equivalent','claim_rewritten_non_equivalent','claim_split','claim_merged']
            totals['ExactApplicable']+=w*app
            totals['SourceExactApplicable']+=w*(app and 'source_set_retained_exact' in j['source_events'])
            outside+=int(not app and 'source_set_retained_exact' in j['source_events'])
    for k,v in totals.items():close(v,g[kind,'audit_HT',k])
    if kind=='edge':assert outside==17
    for view in ['audit_HT','audit_difference','candidate_baseline','candidate_sample_corrected']:
        close(sum(v for (k,vw,metric),v in g.items() if k==kind and vw==view and metric.startswith('disposition_')),n)
        if kind=='node':close(sum(v for (k,vw,metric),v in g.items() if k==kind and vw==view and metric.startswith('outcome_')),n)
q=rows('question_metrics.csv');qi={(r['kind'],r['view'],r['cell_id'],r['question_id'],r['phase']):r for r in q}
for r in rows('paired_condition_differences.csv'):
    if r['status']!='computed':continue
    sample=[a for a in q if a['kind']==r['kind'] and a['view']==r['view'] and a['cell_id']==r['left_cell'] and a['phase']=='all' and (r['question_stratum']=='ALL' or a['question_stratum']==r['question_stratum'])]
    assert len(sample)==int(r['question_n'])
    diffs=[float(a[r['metric']])-float(qi[r['kind'],r['view'],r['right_cell'],a['question_id'],'all'][r['metric']]) for a in sample]
    close(sum(diffs)/len(diffs),r['difference'])
for r in rows('condition_and_stratum_tables.csv'):
    if r['view']=='audit_HT' and r['metric'] in ['EdgeClaimRetention','EdgeExactSourceRetention','EdgeValidSubstitution'] and r['status']=='computed':
        assert 0<=float(r['applicable_rate'])<=1+1e-9
u=rows('union_scope_inventory.csv')
assert sum(int(x['n_truth_claims']) for x in u if x['is_terminal_hop']=='True')==1766
assert sum(int(x['n_truth_claims']) for x in u if x['is_terminal_hop']=='True' and x['requires_multi_node_union']=='True')==1444
assert json.loads((P/'m2_validation.json').read_text(encoding='utf-8'))['failures']==[]
print(json.dumps({'status':'passed','input_hashes':len(m['input_sha256']),'output_hashes':len(m['output_sha256']),'checks':['scope_identity','original_candidates_nonfinal','independent_HT_recomputation','five_category_partition','condition_pairing','edge_rate_domain','union_inventory','M2_payloads']},ensure_ascii=False))
