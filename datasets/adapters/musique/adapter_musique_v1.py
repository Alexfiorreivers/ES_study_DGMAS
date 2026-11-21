#!/usr/bin/env python3
"""MuSiQue-Ans dev -> HM 2.1 structural candidates plus sidecars."""
from __future__ import annotations
import argparse, copy, datetime as dt, hashlib, json, math, os, re, tempfile, uuid
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

DATASET, RELEASE, SPLIT = "MuSiQue", "v1.0", "dev"
QUOTAS = {"2hop": 67, "3hop1": 34, "3hop2": 33, "4hop1": 22, "4hop2": 22, "4hop3": 22}
RAW_FIELDS = {"id", "question", "answer", "answer_aliases", "answerable", "paragraphs", "question_decomposition"}
REF = re.compile(r"#([0-9]+)(?![0-9])")
NUM = re.compile(r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])")
WH = re.compile(r"\b(who|whom|whose|what|which|where|when|why|how)\b", re.I)
LONG_WH = re.compile(r"\bhow\s+(many|much|long)\b", re.I)
COMPARE = re.compile(r"\b(same|different|earlier|later|older|younger|more|less|before|after|larger|smaller|highest|lowest)\b", re.I)
NEG_MODAL = re.compile(r"\b(not|no|never|neither|nor|can|could|will|would|shall|should|may|might|must)\b|n't\b", re.I)
BOUNDARY = re.compile(r";|,|\b(?:and|but|or|who|which|whose)\b", re.I)

class ContractError(ValueError): pass
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
def canon(x): return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
def digest(x): return hashlib.sha256(x).hexdigest()
def file_digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()
def read_json(p):
    with p.open(encoding="utf-8") as f: return json.load(f)
def resolve(value, config_path):
    p = Path(value); return p if p.is_absolute() else (config_path.parent / p).resolve()

def load_config(path):
    c = read_json(path)
    keys = {"config_version","dataset","paths","versions","sampling_seed","run_id_policy","final_quotas","soft_coverage_policy","batch_size","output_format"}
    if keys - c.keys(): raise ContractError(f"missing config keys: {sorted(keys-c.keys())}")
    if c["dataset"] != {"name":DATASET,"release":RELEASE,"split":SPLIT}: raise ContractError("dataset constants differ")
    if c["final_quotas"] != QUOTAS: raise ContractError("six frozen quotas differ")
    if c["versions"].get("schema") != "2.1" or c["versions"].get("sidecar") != "1.0.0": raise ContractError("version binding differs")
    return c

def type_ok(x, t):
    return {"object":lambda:isinstance(x,dict),"array":lambda:isinstance(x,list),"string":lambda:isinstance(x,str),
            "integer":lambda:type(x) is int,"number":lambda:type(x) in (int,float) and math.isfinite(x),
            "boolean":lambda:type(x) is bool,"null":lambda:x is None}.get(t,lambda:True)()

def schema_errors(x, s, root=None, at="$", errors=None):
    """Validate every JSON-Schema keyword used by the bound HM 2.1 schema."""
    root, errors = root or s, [] if errors is None else errors
    if "$ref" in s:
        target = root
        for part in s["$ref"][2:].split("/"): target = target[part.replace("~1","/").replace("~0","~")]
        return schema_errors(x, target, root, at, errors)
    for child in s.get("allOf", []): schema_errors(x, child, root, at, errors)
    if "if" in s:
        probe=[]; schema_errors(x,s["if"],root,at,probe); branch=s.get("then") if not probe else s.get("else")
        if branch: schema_errors(x,branch,root,at,errors)
    if "oneOf" in s:
        hits=0
        for child in s["oneOf"]:
            probe=[]; schema_errors(x,child,root,at,probe); hits += not probe
        if hits != 1: errors.append(f"{at}: oneOf matched {hits}")
        return errors
    if "type" in s:
        choices=s["type"] if isinstance(s["type"],list) else [s["type"]]
        if not any(type_ok(x,t) for t in choices): errors.append(f"{at}: wrong type"); return errors
    if "const" in s and x != s["const"]: errors.append(f"{at}: const mismatch")
    if "enum" in s and x not in s["enum"]: errors.append(f"{at}: enum mismatch")
    if isinstance(x,dict):
        for k in s.get("required",[]):
            if k not in x: errors.append(f"{at}: missing {k}")
        props=s.get("properties",{})
        if s.get("additionalProperties") is False:
            for k in x.keys()-props.keys(): errors.append(f"{at}: extra {k}")
        elif isinstance(s.get("additionalProperties"),dict):
            for k in x.keys()-props.keys(): schema_errors(x[k],s["additionalProperties"],root,f"{at}.{k}",errors)
        for k,v in props.items():
            if k in x: schema_errors(x[k],v,root,f"{at}.{k}",errors)
    if isinstance(x,list):
        if len(x)<s.get("minItems",0): errors.append(f"{at}: too few items")
        if "maxItems" in s and len(x)>s["maxItems"]: errors.append(f"{at}: too many items")
        if s.get("uniqueItems") and len({canon(v) for v in x})!=len(x): errors.append(f"{at}: duplicates")
        if "items" in s:
            for i,v in enumerate(x): schema_errors(v,s["items"],root,f"{at}[{i}]",errors)
    if isinstance(x,str):
        if len(x)<s.get("minLength",0): errors.append(f"{at}: too short")
        if "pattern" in s and not re.search(s["pattern"],x): errors.append(f"{at}: pattern")
    if type(x) in (int,float):
        if "minimum" in s and x<s["minimum"]: errors.append(f"{at}: minimum")
        if "maximum" in s and x>s["maximum"]: errors.append(f"{at}: maximum")
    return errors

def template_for(oid, nsteps):
    m=re.match(r"^(2hop|3hop1|3hop2|4hop1|4hop2|4hop3)__",oid)
    if not m: raise ContractError("unsupported id prefix")
    template=m.group(1); hop="2hop" if template=="2hop" else template[:4]
    if int(hop[0])!=nsteps: raise ContractError("hop prefix/decomposition length mismatch")
    return hop,template

def validate_raw(raw):
    if RAW_FIELDS-raw.keys(): raise ContractError(f"missing fields: {sorted(RAW_FIELDS-raw.keys())}")
    if not isinstance(raw["id"],str) or not isinstance(raw["question"],str): raise ContractError("id/question type")
    if raw["answerable"] is not True or type(raw["answerable"]) is not bool: raise ContractError("answerable is not true")
    if not isinstance(raw["answer_aliases"],list): raise ContractError("answer_aliases type")
    if not isinstance(raw["paragraphs"],list) or not raw["paragraphs"]: raise ContractError("paragraphs shape")
    pmap={}
    for pos,p in enumerate(raw["paragraphs"]):
        idx=p.get("idx")
        if type(idx) is not int or idx<0 or idx in pmap: raise ContractError("paragraph idx invalid/duplicate")
        if not isinstance(p.get("title"),str) or not isinstance(p.get("paragraph_text"),str) or type(p.get("is_supporting")) is not bool: raise ContractError("paragraph fields invalid")
        pmap[idx]=(pos,p)
    steps=raw["question_decomposition"]
    if not isinstance(steps,list) or not steps: raise ContractError("decomposition shape")
    step_ids=set(); used=set()
    for step in steps:
        if not isinstance(step,dict) or not {"id","question","answer","paragraph_support_idx"}<=step.keys(): raise ContractError("step shape")
        if type(step["id"]) is not int or step["id"] in step_ids: raise ContractError("step id invalid/duplicate")
        if not isinstance(step["question"],str): raise ContractError("step question type")
        idx=step["paragraph_support_idx"]
        if type(idx) is not int or idx not in pmap or pmap[idx][1]["is_supporting"] is not True: raise ContractError("step locator invalid")
        step_ids.add(step["id"]); used.add(idx)
    if used!={idx for idx,(_,p) in pmap.items() if p["is_supporting"]}: raise ContractError("support set/decomposition mismatch")
    hop,template=template_for(raw["id"],len(steps)); return pmap,hop,template

def expand_refs(text, current, previous):
    legal=[]; literal=[]; parents=[]; chunks=[]; cursor=0
    for m in REF.finditer(text):
        k=int(m.group(1)); chunks.append(text[cursor:m.start()]); span={"start":m.start(),"end":m.end()}
        if 1<=k<current and k in previous:
            replacement=str(previous[k]["answer"]); chunks.append(replacement)
            legal.append({"step_id":k,"surface":m.group(0),"span":span,"replacement":replacement})
            if k not in parents: parents.append(k)
        else: chunks.append(m.group(0)); literal.append({"surface":m.group(0),"span":span,"step_id_candidate":k})
        cursor=m.end()
    chunks.append(text[cursor:]); return "".join(chunks),legal,parents,literal

def qa_info(text,answer):
    long=list(LONG_WH.finditer(text)); covered=[(m.start(),m.end()) for m in long]
    spans=[{"surface":m.group(0),"span":{"start":m.start(),"end":m.end()}} for m in long]
    kinds=["duration" if m.group(1).lower()=="long" else "quantity" for m in long]
    for m in WH.finditer(text):
        if not any(a<=m.start() and m.end()<=b for a,b in covered):
            spans.append({"surface":m.group(0),"span":{"start":m.start(),"end":m.end()}}); kinds.append(m.group(1).lower())
    flags=[]
    if str(answer).strip().casefold() in {"yes","no"}: flags.append("yes_no_polarity")
    if re.search(r"\bor\b",text,re.I): flags.append("choice_candidate")
    if COMPARE.search(text): flags.append("comparison_candidate")
    if NEG_MODAL.search(text): flags.append("negation_or_modality")
    return sorted(set(kinds or ["unknown"])),spans,sorted(set(flags))

def number_mentions(text,scope,source_ref):
    out=[]
    for m in NUM.finditer(text):
        surface=m.group(0); plain=surface.replace(",",""); kinds=["numeric"]
        if re.fullmatch(r"\d{4}",surface): kinds.append("year_like")
        tail=text[m.end():m.end()+24]; unit=re.match(r"\s*([A-Za-z%]+)",tail)
        out.append({"scope":scope,"source_ref":source_ref,"surface":surface,"span":{"start":m.start(),"end":m.end()},
                    "kind_candidates":kinds,"parsed_values":[float(plain) if "." in plain else int(plain)],
                    "unit":unit.group(1) if unit else None,"precision":len(plain.rsplit(".",1)[1]) if "." in plain else None})
    return out

def protected(text,scope,source_ref,titles,answer):
    out=[]
    for value,kind in [(answer,"answer")]+[(x,"title") for x in titles]:
        if value:
            for m in re.finditer(re.escape(value),text,re.I): out.append({"scope":scope,"source_ref":source_ref,"surface":m.group(0),"span":{"start":m.start(),"end":m.end()},"kind":kind})
    for m in REF.finditer(text): out.append({"scope":scope,"source_ref":source_ref,"surface":m.group(0),"span":{"start":m.start(),"end":m.end()},"kind":"literal_hash_number"})
    for item in number_mentions(text,scope,source_ref): out.append({"scope":scope,"source_ref":source_ref,"surface":item["surface"],"span":item["span"],"kind":"number_unit"})
    unique={(x["scope"],x["source_ref"],x["span"]["start"],x["span"]["end"],x["kind"]):x for x in out}
    return sorted(unique.values(),key=lambda x:(x["scope"],x["source_ref"] or "",x["span"]["start"],x["kind"]))

def split_hints(text,origin_ref,protected_items,start):
    spans=[x["span"] for x in protected_items if x["source_ref"]==origin_ref]; out=[]
    for n,m in enumerate(BOUNDARY.finditer(text)):
        overlap=any(m.start()<x["end"] and x["start"]<m.end() for x in spans)
        out.append({"split_candidate_ref":f"split:{start+n}","origin_ref":origin_ref,"trigger":m.group(0),
                    "span":{"start":m.start(),"end":m.end()},"left_text":text[:m.start()],"right_text":text[m.end():],
                    "protected_overlap":overlap,"recommended":m.group(0)==";" and not overlap and not NEG_MODAL.search(text) and not COMPARE.search(text),
                    "rule_id":"semicolon_boundary" if m.group(0)==";" else "lexical_boundary_recall"})
    return out

def duplicate_titles(paragraphs):
    groups=defaultdict(list)
    for p in paragraphs: groups[p["title"]].append(p["idx"])
    return [{"title":t,"paragraph_indices":v} for t,v in sorted(groups.items()) if len(v)>1]

def coverage(raw,sources,numbers):
    titles=[p["title"] for p in raw["paragraphs"]]; st=[s["title"] for s in sources]; text="\n".join(s["text"] for s in sources); ans=str(raw["answer"])
    relation=[">>" in x["question"] for x in raw["question_decomposition"]]
    fmt="relation_only" if all(relation) else "natural_only" if not any(relation) else "mixed"
    return {"numeric_in_question":any(x["scope"]=="question" for x in numbers),"numeric_in_answer":any(x["scope"]=="answer" for x in numbers),
            "numeric_in_support":any(x["scope"]=="source" for x in numbers),"date_or_year_candidate":any("year_like" in x["kind_candidates"] for x in numbers),
            "comparison_operator_candidate":bool(COMPARE.search(raw["question"])),"answer_alias_present":bool(raw["answer_aliases"]),
            "duplicate_title_in_context":len(set(titles))<len(titles),"duplicate_support_title":len(set(st))<len(st),
            "multiple_answer_occurrences":text.casefold().count(ans.casefold())>1 if ans else False,"decomposition_format":fmt}

def validate_sidecar(sidecar,hm):
    required={"sidecar_version","run_id","sample_id","dataset_name","source_split","raw_record_ref","base_record_sha256","selection","soft_coverage_labels","qa2s_candidates","split_candidates","protected_spans","numeric_mentions","link_candidates","graph_candidates","dataset_specific","structural_validation"}
    if set(sidecar)!=required: raise ContractError("sidecar top-level contract differs")
    if sidecar["sample_id"]!=hm["sample"]["sample_id"] or sidecar["run_id"]!=hm["dataset_manifest"]["run_id"]: raise ContractError("sidecar binding differs")
    if sidecar["base_record_sha256"]!=digest(canon(hm)): raise ContractError("base record hash differs")
    scopes={("question",None):hm["sample"]["question"],("answer",None):str(hm["sample"]["answer"])}
    scopes.update({("source",s["source_id"]):s["text"] for s in hm["sources"]})
    for group in (sidecar["protected_spans"],sidecar["numeric_mentions"]):
        for item in group:
            text=scopes[(item["scope"],item["source_ref"])]; span=item["span"]
            if text[span["start"]:span["end"]]!=item["surface"]: raise ContractError("span replay failed")

def build_record(raw,state,source,file_hash,run_id,cfg,record_index,line_number,schema):
    pmap,hop,template=state; sid=f"{DATASET}:{RELEASE}:{SPLIT}:{raw['id']}"
    documents=[{"context_index":pos,"title":p["title"],"text":p["paragraph_text"],"sentences":[],"is_supporting_context":p["is_supporting"],"raw_locator":{"paragraph_idx":p["idx"],"context_index":pos}} for pos,p in enumerate(raw["paragraphs"])]
    source_by_idx={}; sources=[]
    for pos,step in enumerate(raw["question_decomposition"],1):
        idx=step["paragraph_support_idx"]
        if idx in source_by_idx: continue
        context,p=pmap[idx]; source_id=f"{sid}:source:{len(sources)}"; source_by_idx[idx]=source_id
        related=[i+1 for i,x in enumerate(raw["question_decomposition"]) if x["paragraph_support_idx"]==idx]
        sources.append({"source_id":source_id,"sample_id":sid,"context_index":context,"title":p["title"],"entity_qid":None,"paragraph_idx":idx,"sent_id":None,"char_start":None,"char_end":None,"text":p["paragraph_text"],"granularity":"paragraph","source_origin":"official_gold","raw_locator":{"paragraph_idx":idx,"context_index":context,"decomposition_step_positions":related},"locator_status":"valid"})
    hm={"schema_version":"2.1","processing_stage":"adapter_candidate","dataset_manifest":{"dataset_name":DATASET,"release":RELEASE,"split":SPLIT,"source_file":str(source),"file_sha256":file_hash,"adapter_version":cfg["versions"]["adapter"],"run_id":run_id,"sidecar_version":"1.0.0","schema_version":"2.1"},
        "semantic_screening":{"method":None,"model":None,"reasoning_effort":None,"prompt_version":None,"rule_version":cfg["versions"]["rule"],"screened_at":None,"requires_human_audit":True},
        "sample":{"sample_id":sid,"original_sample_id":raw["id"],"dataset_name":DATASET,"release":RELEASE,"split":SPLIT,"question":raw["question"],"answer":raw["answer"],"question_type":hop,"question_level":None,"answerability":1,"raw_locator":{"source_file":str(source),"record_index":record_index,"line_number":line_number,"original_sample_id":raw["id"]},"normalization_status":"normalized","exclusion_reason":None},
        "documents":documents,"claims":[],"sources":sources,"claim_source_links":[],"reasoning_graph":None,
        "validation":{"status":None,"errors":{},"warnings":{},"validator_version":cfg["versions"]["validator"],"validated_at":None}}
    errors=schema_errors(hm,schema)
    if errors: raise ContractError("HM candidate invalid: "+"; ".join(errors[:8]))
    quota_hash=digest(canon({"config_version":cfg["config_version"],"final_quotas":cfg["final_quotas"],"sampling_seed":cfg["sampling_seed"]}))
    rank_key=digest(f"{cfg['sampling_seed']}|{RELEASE}|{SPLIT}|{raw['id']}".encode())
    previous={}; qa=[]; edges=[]; literals=[]
    for pos,step in enumerate(raw["question_decomposition"],1):
        expanded,legal,parents,literal=expand_refs(step["question"],pos,previous); kinds,spans,flags=qa_info(step["question"],step["answer"])
        if ">>" in step["question"]: flags.append("relation_style_candidate")
        qa.append({"candidate_ref":f"qa2s:step:{pos}","origin_kind":"decomposition_step","origin_source_ids":[source_by_idx[step["paragraph_support_idx"]]],"question":step["question"],"expanded_question":expanded,"answer":step["answer"],"question_kind_candidates":kinds,"wh_spans":spans,"answer_slot":{"surface":step["answer"]},"legal_references":legal,"flags":sorted(set(flags)),"rule_version":cfg["versions"]["qa2s_rule"]})
        edges.extend({"source_step_id":p,"target_step_id":pos} for p in parents); literals.extend({"step_position":pos,**x} for x in literal); previous[pos]=step
    kinds,spans,flags=qa_info(raw["question"],raw["answer"]); all_sources=list(source_by_idx.values())
    qa.append({"candidate_ref":"qa2s:final","origin_kind":"final_qa","origin_source_ids":all_sources,"question":raw["question"],"expanded_question":raw["question"],"answer":raw["answer"],"question_kind_candidates":kinds,"wh_spans":spans,"answer_slot":{"surface":raw["answer"]},"legal_references":[],"flags":flags,"rule_version":cfg["versions"]["qa2s_rule"]})
    scopes=[("question",None,raw["question"]),("answer",None,str(raw["answer"]))]+[("source",s["source_id"],s["text"]) for s in sources]
    titles=[p["title"] for p in raw["paragraphs"]]; protections=[]; numbers=[]
    for scope,ref,text in scopes: protections+=protected(text,scope,ref,titles,str(raw["answer"])); numbers+=number_mentions(text,scope,ref)
    splits=[]
    for s in sources: splits+=split_hints(s["text"],s["source_id"],protections,len(splits))
    links=[{"link_candidate_ref":f"linkcand:{i}","claim_candidate_refs":[q["candidate_ref"]],"source_ids":q["origin_source_ids"],"rule_id":"official_decomposition_paragraph","automatic_match_reason":"official_step_paragraph","semantic_status":"unreviewed"} for i,q in enumerate(qa[:-1])]
    links.append({"link_candidate_ref":f"linkcand:{len(links)}","claim_candidate_refs":["qa2s:final"],"source_ids":all_sources,"rule_id":"official_ancestor_source_closure","automatic_match_reason":"official_step_ancestor_closure","semantic_status":"unreviewed"})
    gedges=[{"edge_candidate_ref":f"edgecand:{i}","source_candidate_refs":[f"qa2s:step:{e['source_step_id']}"],"target_candidate_ref":f"qa2s:step:{e['target_step_id']}","relation_candidate":"inference","rule_id":"official_decomposition_reference","evidence":e} for i,e in enumerate(edges)]
    side={"sidecar_version":"1.0.0","run_id":run_id,"sample_id":sid,"dataset_name":DATASET,"source_split":SPLIT,"raw_record_ref":{"source_file":str(source),"file_sha256":file_hash,"record_index":record_index,"line_number":line_number,"original_sample_id":raw["id"]},"base_record_sha256":digest(canon(hm)),
          "selection":{"sampling_seed":str(cfg["sampling_seed"]),"rank_key":rank_key,"pool_rank":None,"final_quota_cell":{"hop":hop,"template":template},"frozen_quota":{"config_version":cfg["config_version"],"target":QUOTAS[template],"selection_config_sha256":quota_hash}},
          "soft_coverage_labels":coverage(raw,sources,numbers),"qa2s_candidates":qa,"split_candidates":splits,"protected_spans":protections,"numeric_mentions":numbers,"link_candidates":links,"graph_candidates":[{"graph_candidate_ref":"graphcand:0","node_refs":[x["candidate_ref"] for x in qa],"edges":gedges,"origin_hint":"musique_official_decomposition_normalized"}],
          "dataset_specific":{"decomposition_steps":copy.deepcopy(raw["question_decomposition"]),"official_step_edges":edges,"paragraph_idx_map":[{"paragraph_idx":idx,"context_index":pos} for idx,(pos,_) in sorted(pmap.items())],"answer_aliases":copy.deepcopy(raw["answer_aliases"]),"duplicate_title_groups":duplicate_titles(raw["paragraphs"]),"template_signature":template,"literal_hash_references":literals},
          "structural_validation":{"status":"passed","errors":[],"warnings":[],"validator_version":cfg["versions"]["validator"],"validated_at":now()}}
    validate_sidecar(side,hm); return hm,side

def topo_check(edges,count):
    children=defaultdict(list); indegree={i:0 for i in range(1,count+1)}
    for e in edges:
        a,b=e["source_step_id"],e["target_step_id"]
        if a not in indegree or b not in indegree or a==b: raise ContractError("invalid topology")
        children[a].append(b); indegree[b]+=1
    q=deque(x for x,d in indegree.items() if d==0); seen=0
    while q:
        x=q.popleft(); seen+=1
        for child in children[x]:
            indegree[child]-=1
            if indegree[child]==0:q.append(child)
    if seen!=count: raise ContractError("cyclic topology")

def write_json(p,x):
    with p.open("w",encoding="utf-8",newline="\n") as f: json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False); f.write("\n")
def write_jsonl(p,items):
    with p.open("w",encoding="utf-8",newline="\n") as f:
        for x in items:f.write(json.dumps(x,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")

def run(config_path,cfg,dry_run):
    source=resolve(cfg["paths"]["input_jsonl"],config_path); schema_path=resolve(cfg["paths"]["hm_schema"],config_path); template_path=resolve(cfg["paths"]["hm_template"],config_path); output=resolve(cfg["paths"]["output_root"],config_path)
    for p in (source,schema_path,template_path):
        if not p.is_file(): raise ContractError(f"missing input: {p}")
    schema=read_json(schema_path)
    if read_json(template_path).get("schema_version")!="2.1": raise ContractError("template is not 2.1")
    fhash=file_digest(source); expected=cfg["paths"].get("expected_input_sha256")
    if expected is not None and expected!=fhash: raise ContractError("input hash mismatch")
    run_id=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:8]
    pools=defaultdict(list); exclusions=[]; seen=set(); count=0
    with source.open(encoding="utf-8") as f:
        for index,line in enumerate(f):
            count+=1; raw=None
            try:
                if not line.strip(): raise ContractError("blank line")
                raw=json.loads(line)
                if not isinstance(raw,dict): raise ContractError("record is not object")
                if raw.get("id") in seen: raise ContractError("duplicate sample id")
                seen.add(raw.get("id")); state=validate_raw(raw)
                hm,side=build_record(raw,state,source.resolve(),fhash,run_id,cfg,index,index+1,schema)
                topo_check(side["dataset_specific"]["official_step_edges"],len(raw["question_decomposition"])); pools[state[1]].append((hm,side))
            except Exception as exc: exclusions.append({"record_index":index,"line_number":index+1,"original_sample_id":raw.get("id") if isinstance(raw,dict) else None,"reason_code":"structural_validation_failed","details":str(exc)})
    pairs=[x for values in pools.values() for x in values]
    by_template=defaultdict(int)
    for hm,side in sorted(pairs,key=lambda x:(x[1]["selection"]["final_quota_cell"]["template"],x[1]["selection"]["rank_key"])):
        cell=side["selection"]["final_quota_cell"]["template"]; side["selection"]["pool_rank"]=by_template[cell]; by_template[cell]+=1
    summary={"run_id":run_id,"source_file":str(source.resolve()),"file_sha256":fhash,"read_count":count,"passed_count":len(pairs),"excluded_count":len(exclusions),"counts_by_hop":{h:len(pools[h]) for h in ("2hop","3hop","4hop")},"counts_by_template":dict(sorted(by_template.items())),"exclusion_reasons":dict(Counter(x["reason_code"] for x in exclusions)),"dry_run":dry_run}
    if dry_run:return summary
    names=["manifests","candidate_pool","gpt_screened","gpt_judgments","final_silver","exclusions"]
    if output.exists() and any(any((output/n).iterdir()) for n in names if (output/n).exists()): raise ContractError("existing artifacts: refusing overwrite")
    output.parent.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix=".musique_adapter_",dir=output.parent))
    for n in names:(tmp/n).mkdir()
    for hop in ("2hop","3hop","4hop"):
        ordered=sorted(pools[hop],key=lambda x:(x[1]["selection"]["final_quota_cell"]["template"],x[1]["selection"]["rank_key"])); write_jsonl(tmp/"candidate_pool"/f"{hop}.jsonl",[x[0] for x in ordered])
    ordered=sorted(pairs,key=lambda x:(x[1]["selection"]["final_quota_cell"]["template"],x[1]["selection"]["pool_rank"])); write_jsonl(tmp/"candidate_pool"/"sidecars.jsonl",[x[1] for x in ordered]); write_jsonl(tmp/"exclusions"/"excluded_records.jsonl",exclusions)
    sel={"config_version":cfg["config_version"],"sampling_seed":cfg["sampling_seed"],"final_quotas":QUOTAS,"selection_config_sha256":digest(canon({"config_version":cfg["config_version"],"final_quotas":cfg["final_quotas"],"sampling_seed":cfg["sampling_seed"]}))}
    write_json(tmp/"manifests"/"selection_manifest.json",sel); write_json(tmp/"manifests"/"adapter_run_manifest.json",{**summary,"adapter_version":cfg["versions"]["adapter"],"schema_version":"2.1","sidecar_version":"1.0.0","generated_at":now()}); write_json(tmp/"manifests"/"summary_statistics.json",summary)
    for p in tmp.rglob("*.jsonl"):
        with p.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():json.loads(line)
    if output.exists():
        for n in names:
            p=output/n
            if p.exists(): p.rmdir()
        output.rmdir()
    os.replace(tmp,output); return summary

def self_check(config_path):
    cfg=load_config(config_path); schema=read_json(resolve(cfg["paths"]["hm_schema"],config_path))
    raw={"id":"2hop__11_22","question":"Who followed Alpha?","answer":"Beta","answer_aliases":[],"answerable":True,"paragraphs":[{"idx":5,"title":"Alpha","paragraph_text":"Alpha preceded Beta in 2001.","is_supporting":True},{"idx":9,"title":"Beta","paragraph_text":"Beta was active for 2 years.","is_supporting":True}],"question_decomposition":[{"id":11,"question":"Alpha >> successor","answer":"Beta","paragraph_support_idx":5},{"id":22,"question":"How long was #1 active?","answer":"2 years","paragraph_support_idx":9}]}
    hm,side=build_record(raw,validate_raw(raw),Path("fixture.jsonl").resolve(),"a"*64,"fixture_run",cfg,0,1,schema)
    assert not schema_errors(hm,schema); bad=copy.deepcopy(hm); bad["claims"]=[{"bad":1}]; assert schema_errors(bad,schema)
    assert side["qa2s_candidates"][1]["expanded_question"]=="How long was Beta active?"; print("adapter self-check: PASS")

def main():
    p=argparse.ArgumentParser(description="Build MuSiQue HM 2.1 structural candidates; never invokes GPT.")
    p.add_argument("--config",default=str(Path(__file__).with_name("adapter_config.json"))); p.add_argument("--dry-run",action="store_true"); p.add_argument("--self-check",action="store_true")
    a=p.parse_args(); cp=Path(a.config).resolve()
    try:
        if a.self_check:self_check(cp); return 0
        print(json.dumps(run(cp,load_config(cp),a.dry_run),ensure_ascii=False,indent=2)); return 0
    except Exception as exc: print(f"ERROR: {exc}"); return 2
if __name__=="__main__":raise SystemExit(main())
