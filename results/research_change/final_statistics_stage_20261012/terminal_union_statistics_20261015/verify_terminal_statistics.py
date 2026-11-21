"""Independent arithmetic, identity and M2 checks for delivered statistics."""
from pathlib import Path
import json,csv,hashlib,sys,collections,math
P=Path(__file__).resolve().parent;U=P.parent/'terminal_union_primary_20261013';PROJECT=P.parents[2]
sys.path.insert(0,str(PROJECT/'src'))
from agent_lab.m2_contracts import NodeJudgment
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def jl(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fs(x):
 eq=x['claim_presence']=='present_equivalent'
 return dict(CSR=int(eq),ESS=int(x['exact_set_survived'] is True),VSSR=int(x['source_change_status']=='substituted_valid'),AA=int(eq and x['support_fine']=='fully_supported'))
form=j(U/'human_review_form.json');r=jl(P/'terminal_analysis_ledger.jsonl');s=j(P/'analysis_summary.json')
assert len(form)==256 and all(x['human_review']['review_status']=='decided' and x['human_review']['decision']!='needs_review' for x in form)
assert len(r)==1366 and len({x['scope_id'] for x in r})==1366
assert len({x['observation_key'] for x in r})==520 and len({x['question_id'] for x in r})==60
actual={x['item_id']:x for x in jl(U/'union_scope_ledger.jsonl')}
counts={v:collections.defaultdict(float) for v in s['global']};layers=collections.Counter();strata=collections.defaultdict(list)
for x in r:
 src=actual[x['item_id']]
 for k in ['scope_id','question_id','observation_key','truth_claim_id','dataset','condition','replicate_index']:assert x[k]==src[k]
 if x['judgment']:NodeJudgment.model_validate(x['judgment'])
 if x['route']!='simple_proxy_population':
  layers['exact']+=1;f=fs(x['judgment'])
  for v in counts:
   for m,y in f.items():counts[v][m]+=y
 else:
  strata[x['sampling_stratum']].append(x);p=fs(x['frozen_proposal']);h=fs(x['judgment']) if x['sampled'] else None
  layers['sample' if h else 'unreviewed']+=1
  assert bool(h)==bool(x['judgment'])
  for m,y in p.items():
   counts['candidate_anchored'][m]+=y;counts['sample_replaced'][m]+=h[m] if h else y
   counts['audit_difference'][m]+=y+x['weight']*(h[m]-y) if h else y
   if h:counts['audit_HT'][m]+=x['weight']*h[m]
for st,rr in strata.items():
 sampled=[x for x in rr if x['sampled']];assert len(sampled)==min(len(rr),max(2,math.ceil(.1*len(rr))))
 assert all(abs(x['weight']-len(rr)/len(sampled))<1e-10 for x in sampled)
assert layers=={'exact':210,'sample':120,'unreviewed':1036}
for v,dd in counts.items():
 for m,z in dd.items():assert abs(z-s['global'][v][m])<1e-7,(v,m,z)
assert len(jl(P/'human_terminal_judgments_256.jsonl'))==256
# Confirm all paired means are same-question condition mean differences.
cs=list(csv.DictReader((P/'condition_question_macro.csv').open(encoding='utf-8-sig')))
ps=list(csv.DictReader((P/'paired_condition_differences.csv').open(encoding='utf-8-sig')))
for x in ps:
 a,b=x['comparison'].split('-')
 lookup=lambda c:float(next(z['mean'] for z in cs if z['dataset']==x['dataset'] and z['condition']==c and z['view']==x['view'] and z['metric']==x['metric']))
 assert abs(lookup(a)-lookup(b)-float(x['difference']))<1e-10
# Historical frozen files remain unchanged.
frozen=j(U/'manifest.json')
for name,h in frozen['immutable_output_sha256'].items():assert sha(U/name)==h,name
for name,h in frozen['input_sha256'].items():assert sha(Path(name))==h,name
manifest=j(P/'manifest.json')
for name,h in manifest['input_sha256'].items():assert sha(Path(name))==h,name
for name,h in manifest['output_sha256'].items():assert sha(P/name)==h,name
out={'status':'passed','human_reviews_decided':256,'reviewed_or_reused_m2_valid':330,'scope_n':1366,'observation_n':520,'question_n':60,'exact_n':210,'sample_n':120,'unreviewed_n':1036,'all_four_views_independently_recomputed':True,'paired_means_verified':True,'frozen_inputs_and_outputs_unchanged':True,'manifest_hashes_valid':True,'no_pending_author_items':True}
(P/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
