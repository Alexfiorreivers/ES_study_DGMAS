"""Frozen terminal union audit analysis; no labels imputed to unreviewed rows."""
from pathlib import Path
import sys,json,csv,copy,hashlib,collections,platform
sys.path.append(str(Path(sys.base_prefix)/'Lib/site-packages')) # local NumPy; retain venv Pydantic priority
import numpy as np
P=Path(__file__).resolve().parent;U=P.parent/'terminal_union_primary_20261013';PROJECT=P.parents[2]
sys.path.insert(0,str(U));sys.path.insert(0,str(PROJECT/'src'))
import complete_human_review_20261015 as helper
from agent_lab.m2_contracts import NodeJudgment
INPUTS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):INPUTS[str(p)]=sha(p);return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def readl(p):INPUTS[str(p)]=sha(p);return [json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def write(name,x):(P/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def csvout(name,rows):
 if not rows:return
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
METRICS=['CSR','ESS','VSSR','AA','ClaimDropped','SourceMissing','FullSupport','PartialSupport','NotSupport','present_equivalent','present_partial','absent','uninterpretable','decided','missing','semantic_negative']
def features(j):
 assert j['review_status']=='decided'
 eq=j['claim_presence']=='present_equivalent'
 outcome='ClaimDropped' if not eq else 'SourceMissing' if j['source_marker_status'] in ['absent','unidentifiable'] else 'FullSupport' if j['support_fine']=='fully_supported' else 'PartialSupport' if j['support_fine']=='partially_supported' else 'NotSupport'
 d={'CSR':eq,'ESS':j['exact_set_survived'] is True,'VSSR':j['source_change_status']=='substituted_valid','AA':eq and j['support_fine']=='fully_supported',outcome:1,j['claim_presence']:1,j['disposition']:1}
 return np.array([float(d.get(k,0)) for k in METRICS])
def human(f,r):
 h=f['human_review'];assert h['decision']!='needs_review' and h['review_status']=='decided'
 j=copy.deepcopy(r['proposal'] or r['component_judgments'][0]['judgment'])
 for k in ['claim_presence','semantic_equivalence','interpretable','source_marker_status','runtime_source_ids','exact_set_survived','source_change_status','support_fine','content_truth','qualification_change','unsupported_spans','disposition','review_status','review_reason_codes']:j[k]=h[k]
 j.update(judgment_id='human_terminal_'+r['scope_id'],node_id=r['scope_id'],scope_kind='terminal_union',scope_node_ids=r['terminal_node_ids'],truth_claim_id=r['truth_claim_id'],canonical_source_ids=r['canonical_source_ids'],origin='manual',is_final=False,annotator_id=h['reviewer_id'],created_at=h['reviewed_at'],rationale=h['rationale'],candidate_id=r['proposal']['candidate_id'] if r['proposal'] else None)
 j['alignment']={'alignment_id':'human_align_'+r['scope_id'],'alignment_type':h['alignment_type'],'runtime_claim_ids':h['aligned_terminal_occurrence_ids'],'truth_claim_ids':h['aligned_truth_claim_ids']}
 NodeJudgment.model_validate(j);return j
def main():
 rows=readl(U/'union_scope_ledger.jsonl');form=read(U/'human_review_form.json');forms={f['item_id']:f for f in form};corrections={r['item_id']:r['judgment'] for r in read(U/'union_reuse_author_corrections_20261015.json')}
 read(U/'manifest.json');read(P/'ANALYSIS_SPEC.md') if False else None
 for p in [P/'ANALYSIS_SPEC.md',Path(__file__),U/'complete_human_review_20261015.py',U/'human_review_reason.md',U/'completion_20261015/original_human_review_reason.md',U/'completion_20261015/original_human_review_form.json',U/'UNION_RULES_AND_AUDIT_PLAN.md',PROJECT/'src/agent_lab/m2_contracts.py']:INPUTS[str(p)]=sha(p)
 questions={x['question_id']:x for x in readl(PROJECT/'research_change/frozen_v1/selected_questions.jsonl')}
 n=len(rows);assert n==1366 and len(forms)==256
 exact=np.array([r['route']!='simple_proxy_population' for r in rows]);sample=np.array([r['item_id'] in forms and not exact[i] for i,r in enumerate(rows)]);known=exact|sample;unknown=~known
 assert (exact.sum(),sample.sum(),unknown.sum())==(210,120,1036)
 y=np.zeros((n,len(METRICS)));proxy=y.copy();weights=np.zeros(n);judgments={};lineage=[];source_errors=[]
 strata=collections.defaultdict(list)
 for i,r in enumerate(rows):
  k=r['item_id'];o=read(U/r['observation_evidence_file']);t=read(U/r['question_evidence_file'])['truth_view']
  r['question_stratum']='|'.join(map(str,questions[r['question_id']]['stratum']));r['n_truth']=len(t['truth_claims'])
  j=human(forms[k],r) if k in forms else corrections.get(k,r['proposal']) if exact[i] else None
  if j:
   NodeJudgment.model_validate(j);assert set(j['alignment']['runtime_claim_ids'])<={c['occurrence_id'] for c in o['terminal_occurrences']}
   actual,links=helper.resolve_sources(k,j['alignment']['runtime_claim_ids'],o,t);canon=helper.canonical_map(t)
   if j['claim_presence']=='present_equivalent' and {helper.source_key(s,canon) for s in actual}!={helper.source_key(s,canon) for s in j['runtime_source_ids']}:source_errors.append(k)
   judgments[k]=j;y[i]=features(j)
  if exact[i]:proxy[i]=y[i];weights[i]=1
  else:
   proxy[i]=features(r['proposal']);strata[r['sampling_stratum']].append(i)
   if sample[i]:weights[i]=r['sampling']['expansion_weight']
  lineage.append({**{k:r[k] for k in ['item_id','scope_id','dataset','condition','replicate_index','observation_key','question_id','truth_claim_id','question_stratum']},'n_truth':r['n_truth'],'route':r['route'],'sampled':bool(sample[i]),'weight':weights[i],'sampling_stratum':r.get('sampling_stratum'),'judgment':j,'frozen_proposal':r['proposal'],'union_reuse_corrected':k in corrections})
 assert not source_errors,source_errors
 (P/'terminal_analysis_ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in lineage),encoding='utf-8')
 (P/'human_terminal_judgments_256.jsonl').write_text(''.join(json.dumps(judgments[f['item_id']],ensure_ascii=False)+'\n' for f in form),encoding='utf-8')
 views={'audit_HT':y*weights[:,None],'candidate_anchored':proxy,'sample_replaced':np.where(known[:,None],y,proxy),'audit_difference':proxy+sample[:,None]*weights[:,None]*(y-proxy)}
 se_cache={}
 def estimate(coeff,view):
  val=coeff@views[view];variance=np.zeros(len(METRICS))
  if view in ['audit_HT','audit_difference']:
   for st,ii in strata.items():
    si=[i for i in ii if sample[i]];N=len(ii);nn=len(si)
    z=coeff[si,None]*(y[si] if view=='audit_HT' else y[si]-proxy[si])
    variance+=N*N*(1-nn/N)*z.var(axis=0,ddof=1)/nn
   return val,np.sqrt(variance)
  return val,None
 tables=[]
 def add(group_type,label,coeff,**meta):
  for view in views:
   val,se=estimate(coeff,view)
   for k,m in enumerate(MR:=METRICS):
    tables.append(dict(group_type=group_type,group=label,view=view,metric=m,estimate=float(val[k]),audit_design_se=float(se[k]) if se is not None else None,audit_design_95_low=float(val[k]-1.96*se[k]) if se is not None else None,audit_design_95_high=float(val[k]+1.96*se[k]) if se is not None else None,**meta))
  lower=coeff[known]@y[known]+np.minimum(coeff[unknown],0).sum();upper=coeff[known]@y[known]+np.maximum(coeff[unknown],0).sum()
  for k,m in enumerate(METRICS[:4]):bounds.append(dict(group_type=group_type,group=label,metric=m,lower=float(lower[k]),upper=float(upper[k]),**meta))
 bounds=[];add('scope_count','all',np.ones(n),scope_n=n)
 layer_rows=[]
 masks={'direct_reuse_74':np.array([r['route']=='human_backed_view_reuse' for r in rows]),'mandatory_136':np.array([r['route']=='mandatory_union_adjudication' for r in rows]),'sample_observed_120':sample,'known_all_330':known}
 for name,mask in masks.items():
  for k,m in enumerate(METRICS):layer_rows.append({'layer':name,'metric':m,'count':float(y[mask,k].sum()),'denominator':int(mask.sum()),'rate':float(y[mask,k].mean()),'is_estimate':False})
 for name,w,den in [('simple_population_estimated_1156',sample*weights,1156),('unreviewed_estimated_1036',sample*(weights-1),1036)]:
  for k,m in enumerate(METRICS):layer_rows.append({'layer':name,'metric':m,'count':float(w@y[:,k]),'denominator':den,'rate':float(w@y[:,k]/den),'is_estimate':True})
 csvout('observed_and_expanded_counts.csv',layer_rows)
 allocation=[];agreements=[];disagreements=[]
 comparison_fields=['claim_presence','source_marker_status','runtime_source_ids','source_change_status','exact_set_survived','support_fine','content_truth','disposition','alignment']
 def fieldval(j,key):
  if key=='alignment':return (j['alignment']['alignment_type'],tuple(sorted(j['alignment']['runtime_claim_ids'])),tuple(sorted(j['alignment']['truth_claim_ids'])))
  if key=='runtime_source_ids':return tuple(sorted(j[key]))
  return j[key]
 for st,ii in strata.items():
  si=[i for i in ii if sample[i]];N=len(ii);nn=len(si);assert nn>=2 and all(abs(weights[i]-N/nn)<1e-9 for i in si)
  allocation.append({'stratum':st,'population_n':N,'sample_n':nn,'unreviewed_n':N-nn,'weight':N/nn})
 for i in np.flatnonzero(sample):
  r=rows[i];j=judgments[r['item_id']];p=r['proposal'];diff=[k for k in comparison_fields if fieldval(j,k)!=fieldval(p,k)]
  if diff:disagreements.append({'item_id':r['item_id'],'stratum':r['sampling_stratum'],'weight':weights[i],'different_fields':diff,'before':{k:p[k] for k in diff},'after':{k:j[k] for k in diff}})
 for group,ii in [('all',list(np.flatnonzero(sample)))]+[(st,[i for i in inds if sample[i]]) for st,inds in strata.items()]:
  for field in comparison_fields+METRICS[:4]+['all_nine_fields']:
   flags=[]
   for i in ii:
    j=judgments[rows[i]['item_id']];p=rows[i]['proposal']
    flags.append(all(fieldval(j,k)==fieldval(p,k) for k in comparison_fields) if field=='all_nine_fields' else features(j)[METRICS.index(field)]==features(p)[METRICS.index(field)] if field in METRICS[:4] else fieldval(j,field)==fieldval(p,field))
   w=weights[ii];flags=np.array(flags,dtype=float)
   agreements.append({'stratum':group,'field':field,'sample_n':len(ii),'matched_n':int(flags.sum()),'unweighted_agreement':float(flags.mean()),'represented_n':float(w.sum()),'weighted_agreement':float(w@flags/w.sum()),'estimated_mismatched_population':float(w@(1-flags))})
 csvout('sampling_allocation.csv',allocation);csvout('simple_proxy_agreement.csv',agreements);write('simple_proxy_disagreements.json',disagreements)
 # Observation, question, condition, and question-type tables retain denominators.
 obsrows=[];qrows=[];conditions=[];pairrows=[];rng=np.random.default_rng(20261015)
 qindex=collections.defaultdict(list)
 for i,r in enumerate(rows):qindex[(r['dataset'],r['condition'],r['question_id'])].append(i)
 for (ds,c,q),ii in qindex.items():
  assert {rows[i]['replicate_index'] for i in ii}=={1,2}
  coeff=np.zeros(n);coeff[ii]=1/len(ii)
  for v in views:
   vals=coeff@views[v];qrows.append({'dataset':ds,'condition':c,'question_id':q,'question_stratum':rows[ii[0]]['question_stratum'],'view':v,**dict(zip(METRICS,map(float,vals)))})
 byobs=collections.defaultdict(list)
 for i,r in enumerate(rows):byobs[r['observation_key']].append(i)
 for ob,ii in byobs.items():
  r=rows[ii[0]];assert len(ii)==r['n_truth']
  for v in views:obsrows.append({**{k:r[k] for k in ['dataset','condition','replicate_index','question_id','observation_key']},'view':v,'truth_scope_n':len(ii),**dict(zip(METRICS,map(float,views[v][ii].sum(axis=0)/len(ii))))})
 for ds in sorted({r['dataset'] for r in rows}):
  qs=sorted({r['question_id'] for r in rows if r['dataset']==ds});nq=len(qs);cs=['M','B0','B1']+(['A1','A2'] if ds=='2wiki' else [])
  qstr=[ '|'.join(map(str,questions[q]['stratum'])) for q in qs];bs=np.zeros((5000,nq))
  for st in sorted(set(qstr)):
   ix=np.array([i for i,x in enumerate(qstr) if x==st]);draw=rng.choice(ix,size=(5000,len(ix)),replace=True)
   for b in range(5000):bs[b]+=np.bincount(draw[b],minlength=nq)/nq
  arrays={}
  for c in cs:
   ii=[i for i,r in enumerate(rows) if r['dataset']==ds and r['condition']==c]
   coeff=np.zeros(n)
   for q in qs:
    inds=qindex[(ds,c,q)];coeff[inds]=1/nq/len(inds)
   add('question_macro',ds+'|'+c,coeff,dataset=ds,condition=c,question_n=nq,scope_n=len(ii))
   sc=np.zeros(n);sc[ii]=1/len(ii);add('scope_rate',ds+'|'+c,sc,dataset=ds,condition=c,question_n=nq,scope_n=len(ii))
   for st in sorted(set(qstr)):
    subqs=[q for q,s in zip(qs,qstr) if s==st];subcoef=np.zeros(n)
    for q in subqs:
     inds=qindex[(ds,c,q)];subcoef[inds]=1/len(subqs)/len(inds)
    add('question_stratum_macro',ds+'|'+c+'|'+st,subcoef,dataset=ds,condition=c,question_stratum=st,question_n=len(subqs))
   for v in views:
    arr=np.array([[next(z for z in qrows if z['dataset']==ds and z['condition']==c and z['question_id']==q and z['view']==v)[m] for m in METRICS[:4]] for q in qs]);arrays[c,v]=arr;boot=bs@arr
    for k,m in enumerate(METRICS[:4]):conditions.append({'dataset':ds,'condition':c,'view':v,'metric':m,'question_n':nq,'mean':float(arr[:,k].mean()),'question_bootstrap_95_low':float(np.quantile(boot[:,k],.025)),'question_bootstrap_95_high':float(np.quantile(boot[:,k],.975)),'out_of_range_question_contributions':int(((arr[:,k]<0)|(arr[:,k]>1)).sum())})
  for c in cs[1:]:
   coeff=np.zeros(n)
   for q in qs:
    for cc,sign in [('M',1),(c,-1)]:
     inds=qindex[ds,cc,q];coeff[inds]=sign/nq/len(inds)
   add('paired_macro_difference',ds+'|M-'+c,coeff,dataset=ds,comparison='M-'+c,question_n=nq)
   for v in views:
    arr=arrays['M',v]-arrays[c,v];boot=bs@arr
    for k,m in enumerate(METRICS[:4]):pairrows.append({'dataset':ds,'comparison':'M-'+c,'view':v,'metric':m,'question_n':nq,'difference':float(arr[:,k].mean()),'question_bootstrap_95_low':float(np.quantile(boot[:,k],.025)),'question_bootstrap_95_high':float(np.quantile(boot[:,k],.975))})
 csvout('estimates_and_audit_uncertainty.csv',tables);csvout('condition_question_macro.csv',conditions);csvout('paired_condition_differences.csv',pairrows);csvout('question_metrics.csv',qrows);csvout('observation_metrics.csv',obsrows);csvout('unreviewed_worst_case_bounds.csv',bounds)
 # Exact sanity identities; no imputation outside sampled rows.
 assert len(byobs)==520 and len(qindex)==260
 assert abs(weights.sum()-n)<1e-8 and abs(weights[sample].sum()-1156)<1e-8
 for v in views:
  assert np.allclose(views[v][:,4:9].sum(axis=1), (weights if v=='audit_HT' else np.ones(n)))
  assert np.allclose(views[v][:,3],views[v][:,6])
 summary={'scope_n':n,'question_n':len({r['question_id'] for r in rows}),'observation_n':len(byobs),'direct_reuse_n':74,'reuse_corrections_n':len(corrections),'mandatory_n':136,'sample_n':120,'simple_population_n':1156,'unreviewed_n':1036,'audit_strata_n':len(strata),'all_human_reviews_decided':True,'validated_reviewed_and_reused_n':len(judgments),'source_identity_errors':source_errors,'global':{v:dict(zip(METRICS,map(float,arr.sum(axis=0)))) for v,arr in views.items()},'python':platform.python_version(),'numpy':np.__version__,'bootstrap_n':5000,'bootstrap_seed':20261015,'sample_changed_n':len(disagreements),'sample_changed_items':[r['item_id'] for r in disagreements],'agreement_all_nine':next(r for r in agreements if r['stratum']=='all' and r['field']=='all_nine_fields')}
 write('analysis_summary.json',summary)
 write('manifest.json',{'input_sha256':INPUTS,'output_sha256':{p.name:sha(p) for p in P.iterdir() if p.is_file() and p.name not in ['manifest.json']}})
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
