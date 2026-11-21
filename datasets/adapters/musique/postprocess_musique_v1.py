#!/usr/bin/env python3
"""Validate GPT judgments, stage HM records, assemble MuSiQue silver, and audit quotas."""
from __future__ import annotations
import argparse, copy, json, os, tempfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from adapter_musique_v1 import (ContractError, QUOTAS, canon, digest, file_digest,
    load_config, now, read_json, resolve, schema_errors, validate_sidecar, write_json, write_jsonl)

JUDGMENT_VERSION="1.0.0"
AMENDMENT_NAME="quota_amendment_v1.0.0.json"
APPROVED_EFFECTIVE_QUOTAS={"2hop":67,"3hop1":34,"3hop2":33,"4hop1":23,"4hop2":20,"4hop3":23}
DECISIONS={"qualified","rejected","review_required"}
SUPPORT_LABELS={"supported_direct","supported_joint","premise_only","partially_supported","mismatch","insufficient"}
CLAIM_CHECKS={"interpretable","faithful","complete","atomic","self_contained","reasons"}

def read_jsonl(path):
    out=[]
    with path.open(encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if line.strip():
                value=json.loads(line)
                if not isinstance(value,dict): raise ContractError(f"{path}:{line_no} is not object")
                out.append(value)
    return out

def load_quota_policy(root):
    manifests=root/"manifests"; path=manifests/AMENDMENT_NAME
    if not path.is_file(): raise ContractError(f"approved quota amendment missing: {path}")
    amendment=read_json(path)
    if amendment.get("amendment_version")!="1.0.0" or amendment.get("status")!="approved": raise ContractError("quota amendment version/status invalid")
    adapter_manifest=read_json(manifests/"adapter_run_manifest.json"); selection=read_json(manifests/"selection_manifest.json")
    run_id=adapter_manifest.get("run_id"); binding=amendment.get("binding",{})
    if amendment.get("scope",{}).get("run_id")!=run_id: raise ContractError("quota amendment run_id mismatch")
    if amendment.get("original_quotas")!=QUOTAS or selection.get("final_quotas")!=QUOTAS: raise ContractError("amendment/Adapter original quotas mismatch")
    effective=amendment.get("effective_quotas")
    if effective!=APPROVED_EFFECTIVE_QUOTAS or sum(effective.values())!=200: raise ContractError("effective quotas are not approved 67/34/33/23/20/23")
    if sum(effective[x] for x in ("4hop1","4hop2","4hop3"))!=66: raise ContractError("effective 4hop total is not 66")
    if binding.get("selection_config_sha256")!=selection.get("selection_config_sha256"): raise ContractError("amendment selection hash mismatch")
    bound={"adapter_run_manifest_file_sha256":manifests/"adapter_run_manifest.json","selection_manifest_file_sha256":manifests/"selection_manifest.json","gpt_batch_sample_ids_file_sha256":manifests/"gpt_batch_sample_ids.json","gpt_input_hashes_file_sha256":manifests/"gpt_input_hashes.json"}
    for field,bound_path in bound.items():
        if binding.get(field)!=file_digest(bound_path): raise ContractError(f"amendment file binding mismatch: {field}")
    judgment_files=[]
    for judgment_path in sorted((root/"gpt_judgments").glob("*/batch_*.json")):
        batch=read_json(judgment_path); judgment_files.append({"cell":batch.get("primary_stratum"),"batch_id":batch.get("batch_id"),"path":str(judgment_path.resolve()),"sha256":file_digest(judgment_path)})
    judgment_files.sort(key=lambda x:(list(QUOTAS).index(x["cell"]) if x["cell"] in QUOTAS else 999,x["batch_id"] or ""))
    if binding.get("judgment_file_count")!=len(judgment_files) or binding.get("judgment_set_sha256")!=digest(canon(judgment_files)): raise ContractError("amendment judgment set binding mismatch")
    return dict(effective),{"path":str(path.resolve()),"sha256":file_digest(path),"amendment_id":amendment.get("amendment_id")}

def verify_batch(batch,candidate_path,sidecar_path,schema):
    required={"judgment_schema_version","run_id","batch_id","dataset_name","primary_stratum","input_binding","screening","sample_ids","judgments","summary"}
    if set(batch)!=required: raise ContractError(f"batch top-level fields differ: {sorted(set(batch)^required)}")
    if batch["judgment_schema_version"]!=JUDGMENT_VERSION or batch["dataset_name"]!="MuSiQue": raise ContractError("batch version/dataset mismatch")
    if batch["primary_stratum"] not in QUOTAS: raise ContractError("unknown hard quota stratum")
    binding=batch["input_binding"]
    if binding.get("hm_schema_version")!="2.1" or binding.get("sidecar_version")!="1.0.0": raise ContractError("batch HM/sidecar binding mismatch")
    if binding.get("candidate_file_sha256")!=file_digest(candidate_path) or binding.get("sidecar_file_sha256")!=file_digest(sidecar_path): raise ContractError("batch input file hash mismatch")
    candidates=indexed(read_jsonl(candidate_path),lambda_key("sample.sample_id"),"candidate sample_id")
    sidecars=indexed(read_jsonl(sidecar_path),"sample_id","sidecar sample_id")
    ids=batch["sample_ids"]
    if not isinstance(ids,list) or len(ids)!=len(set(ids)) or any(not isinstance(x,str) for x in ids): raise ContractError("batch sample_ids invalid")
    judgments=indexed(batch["judgments"],"sample_id","judgment sample_id")
    if set(ids)!=set(judgments): raise ContractError("sample_ids/judgments are not complete one-to-one")
    for sid in ids:
        if sid not in candidates or sid not in sidecars: raise ContractError(f"unknown batch sample: {sid}")
        base=candidates[sid]; side=sidecars[sid]
        if base["processing_stage"]!="adapter_candidate": raise ContractError("mark input is not adapter_candidate")
        validate_sidecar(side,base)
        if side["selection"]["final_quota_cell"]["template"]!=batch["primary_stratum"]: raise ContractError("sample is outside batch quota stratum")
        if batch["run_id"]!=base["dataset_manifest"]["run_id"] or side["run_id"]!=batch["run_id"]: raise ContractError("run_id mismatch")
        if side["base_record_sha256"]!=judgments[sid].get("input_binding",{}).get("base_record_sha256"): raise ContractError("per-record base hash mismatch")
        if judgments[sid].get("input_binding",{}).get("sidecar_sample_id")!=sid: raise ContractError("per-record sidecar binding mismatch")
        validate_judgment(judgments[sid],base,side)
    summary=batch["summary"]
    counts={d:sum(j["decision"]==d for j in judgments.values()) for d in DECISIONS}
    expected={"input_count":len(ids),"processed_count":len(ids),"qualified_count":counts["qualified"],"rejected_count":counts["rejected"],"review_required_count":counts["review_required"]}
    for k,v in expected.items():
        if summary.get(k)!=v: raise ContractError(f"summary {k} is not recomputable")
    if summary.get("unprocessed_sample_ids")!=[]: raise ContractError("batch includes unprocessed ids")
    return candidates,sidecars,judgments

def lambda_key(path):
    parts=path.split(".")
    def get(x):
        for part in parts:x=x.get(part,{})
        return x
    return get

def indexed(items,key,label):
    getter=lambda_key(key) if isinstance(key,str) and "." in key else (lambda x:x.get(key)) if isinstance(key,str) else key
    out={}
    for x in items:
        value=getter(x)
        if not isinstance(value,str) or not value or value in out: raise ContractError(f"invalid/duplicate {label}: {value}")
        out[value]=x
    return out

def validate_minimum(support,source_ids):
    selected=support.get("selected_source_ids")
    if not isinstance(selected,list) or not selected or len(selected)!=len(set(selected)) or any(x not in source_ids for x in selected): raise ContractError("selected_source_ids invalid")
    sufficient=support.get("is_sufficient")
    if type(sufficient) is not bool or type(support.get("if_minimum")) is not bool: raise ContractError("sufficiency/minimum must be booleans")
    tests=support.get("minimum_tests")
    if not isinstance(tests,list): raise ContractError("minimum_tests missing")
    if not sufficient:
        if support["if_minimum"] or tests: raise ContractError("insufficient support cannot be minimum/tested")
    else:
        if [x.get("removed_source_id") for x in tests]!=selected: raise ContractError("minimum tests must follow exact source order")
        for i,test in enumerate(tests):
            if test.get("remaining_source_ids")!=selected[:i]+selected[i+1:] or type(test.get("is_sufficient_after_removal")) is not bool or not isinstance(test.get("reason"),str) or not test["reason"].strip(): raise ContractError("minimum test is incomplete/inconsistent")
        if support["if_minimum"] != all(not x["is_sufficient_after_removal"] for x in tests): raise ContractError("if_minimum contradicts leave-one-out tests")
    alternatives=support.get("alternative_minimum_sets")
    if not isinstance(alternatives,list): raise ContractError("alternative_minimum_sets missing")
    for alt in alternatives:
        proxy={"selected_source_ids":alt.get("source_ids"),"is_sufficient":alt.get("is_sufficient"),"if_minimum":alt.get("if_minimum"),"minimum_tests":alt.get("minimum_tests"),"alternative_minimum_sets":[],"support_reason":alt.get("support_reason")}
        validate_minimum(proxy,source_ids)
    if not isinstance(support.get("support_reason"),str) or not support["support_reason"].strip(): raise ContractError("support_reason missing")

def validate_judgment(j,base,side):
    required={"sample_id","input_binding","decision","claim_proposals","support_judgments","graph_judgment","partial_repair","modifications","confidence","requires_human_review"}
    if set(j)!=required: raise ContractError("judgment fields differ")
    if j["decision"] not in DECISIONS or type(j["requires_human_review"]) is not bool: raise ContractError("decision/review invalid")
    if j["decision"]=="qualified" and j["requires_human_review"]: raise ContractError("qualified cannot have unresolved human review")
    if j["decision"]!="qualified" and not j["requires_human_review"] and j["decision"]=="review_required": raise ContractError("review_required must require review")
    proposals=indexed(j["claim_proposals"],"local_ref","claim local_ref")
    source_ids={x["source_id"] for x in base["sources"]}; candidate_refs={x["candidate_ref"] for x in side["qa2s_candidates"]}
    final=[]
    for p in proposals.values():
        if not isinstance(p.get("claim_text"),str) or not p["claim_text"].strip(): raise ContractError("empty claim_text")
        if not isinstance(p.get("origin_candidate_refs"),list) or any(x not in candidate_refs for x in p["origin_candidate_refs"]): raise ContractError("unknown origin candidate")
        if p.get("derivation_operator") not in {"decomposition_qa_to_statement","qa_to_statement"}: raise ContractError("unknown derivation operator")
        checks=p.get("claim_checks")
        if not isinstance(checks,dict) or set(checks)!=CLAIM_CHECKS or any(type(checks[x]) is not bool for x in CLAIM_CHECKS-{"reasons"}) or not isinstance(checks["reasons"],list): raise ContractError("claim checks invalid")
        if p.get("is_final") is True: final.append(p["local_ref"])
    if j["decision"]=="qualified" and (not proposals or len(final)!=1 or any(not all(p["claim_checks"][x] for x in CLAIM_CHECKS-{"reasons"}) for p in proposals.values())): raise ContractError("qualified claims/final/checks invalid")
    supports=indexed(j["support_judgments"],"support_ref","support ref")
    for s in supports.values():
        if s.get("claim_local_ref") not in proposals or s.get("label") not in SUPPORT_LABELS: raise ContractError("support claim/label invalid")
        if not isinstance(s.get("unsupported_spans"),list): raise ContractError("unsupported_spans missing")
        validate_minimum(s,source_ids)
        if j["decision"]=="qualified" and s["label"] in {"partially_supported","mismatch","insufficient"}: raise ContractError("qualified has unresolved support")
    if j["decision"]=="qualified" and set(x["claim_local_ref"] for x in supports.values())!=set(proposals): raise ContractError("every accepted claim needs support judgment")
    graph=j["graph_judgment"]
    graph_keys={"final_claim_ref","node_refs","accepted_edges","rejected_candidate_edges","bridge_entity","comparison_operator","shortcut_detected","reason"}
    if not isinstance(graph,dict) or set(graph)!=graph_keys or graph.get("final_claim_ref") not in proposals or set(graph.get("node_refs",[]))!=set(proposals): raise ContractError("graph judgment invalid")
    if type(graph.get("shortcut_detected")) is not bool or not isinstance(graph.get("reason"),str) or not graph["reason"].strip(): raise ContractError("graph audit missing")
    for edge in graph["accepted_edges"]:
        if set(edge)!={"source_node_refs","target_node_ref","relation","reason"}: raise ContractError("edge shape invalid")
        refs=edge["source_node_refs"]
        if not refs or len(refs)!=len(set(refs)) or any(x not in proposals for x in refs) or edge["target_node_ref"] not in proposals or edge["target_node_ref"] in refs or edge["relation"] not in {"inference","comparison"} or not isinstance(edge["reason"],str) or not edge["reason"].strip(): raise ContractError("edge invalid")
    for edge in graph["rejected_candidate_edges"]:
        if not isinstance(edge,dict) or not isinstance(edge.get("reason"),str) or not edge["reason"].strip(): raise ContractError("rejected edge needs an auditable reason")
    if j["decision"]=="qualified":
        children=defaultdict(set)
        for edge in graph["accepted_edges"]:
            for source in edge["source_node_refs"]: children[source].add(edge["target_node_ref"])
        final_ref=graph["final_claim_ref"]
        for start in proposals:
            frontier=[start]; reached=set()
            while frontier:
                node=frontier.pop()
                if node in reached: continue
                reached.add(node); frontier.extend(children[node]-reached)
            if final_ref not in reached: raise ContractError("accepted claim does not contribute to final claim")
    repair=j["partial_repair"]
    if set(repair)!={"attempted","attempt_count","before","after_claim_refs","result"} or repair["attempt_count"] not in {0,1} or repair["attempted"]!=(repair["attempt_count"]==1): raise ContractError("partial repair invalid")
    if j["decision"]=="qualified" and repair["attempted"] and repair["result"]!="fully_supported": raise ContractError("unresolved partial repair")
    confidence=j["confidence"]
    if set(confidence)!={"label","uncertainty_reasons"} or confidence["label"] not in {"high","medium","low"} or not isinstance(confidence["uncertainty_reasons"],list): raise ContractError("confidence invalid")
    if j["decision"]=="qualified" and confidence["uncertainty_reasons"]: raise ContractError("qualified has explicit uncertainty")
    if not isinstance(j["modifications"],list): raise ContractError("modifications must be an array")

def marked_record(base,batch):
    out=copy.deepcopy(base); screening=batch["screening"]
    required={"method","model","reasoning_effort","prompt_version","rule_version","screened_at"}
    if set(screening)!=required or screening.get("method")!="gpt" or not all(screening.get(k) for k in required-{"reasoning_effort"}) or screening.get("reasoning_effort") not in {"low","medium","high","xhigh","max","ultra"}: raise ContractError("screening provenance invalid")
    out["processing_stage"]="gpt_screened"; out["semantic_screening"]={**screening,"requires_human_audit":True}
    return out

def mark_command(args,cfg_path,cfg):
    batch=read_json(Path(args.batch)); candidate=Path(args.candidate).resolve(); sidecars=Path(args.sidecars).resolve(); schema=read_json(resolve(cfg["paths"]["hm_schema"],cfg_path))
    candidates,_,judgments=verify_batch(batch,candidate,sidecars,schema)
    completed=[]
    for sid in batch["sample_ids"]:
        record=marked_record(candidates[sid],batch); errors=schema_errors(record,schema)
        if errors: raise ContractError("gpt_screened schema failure: "+"; ".join(errors[:8]))
        completed.append(record)
    if args.dry_run: print(json.dumps({"validated":len(completed),"would_mark":"gpt_screened"},ensure_ascii=False)); return
    output=resolve(cfg["paths"]["output_root"],cfg_path)/"gpt_screened"/f"{batch['primary_stratum']}.jsonl"; output.parent.mkdir(parents=True,exist_ok=True)
    existing=read_jsonl(output) if output.exists() else []; existing_by=indexed(existing,"sample.sample_id","existing screened sample") if existing else {}
    for item in completed:
        sid=item["sample"]["sample_id"]
        if sid in existing_by:
            if canon(existing_by[sid])!=canon(item): raise ContractError("conflicting repeated stage update")
        else: existing.append(item)
    atomic_jsonl(output,existing); print(json.dumps({"marked":len(completed),"output":str(output)},ensure_ascii=False))

def derive_graph(edges,order):
    known=set(order); parents={x:set() for x in order}; incoming=defaultdict(list); children=defaultdict(list); indegree={x:0 for x in order}
    for edge in edges:
        src=edge["source_node_ids"]; target=edge["target_node_id"]
        if not src or len(src)!=len(set(src)) or target not in known or any(x not in known or x==target for x in src): raise ContractError("final edge invalid")
        parents[target].update(src); incoming[target].append(edge)
        for x in src: children[x].append(target); indegree[target]+=1
    q=deque(x for x in order if indegree[x]==0); topo=[]
    while q:
        x=q.popleft(); topo.append(x)
        for child in children[x]:
            indegree[child]-=1
            if indegree[child]==0:q.append(child)
    if len(topo)!=len(order): raise ContractError("claim graph is cyclic")
    depth={x:1 for x in order}
    for target in topo:
        for edge in incoming[target]:
            base=max(depth[x] for x in edge["source_node_ids"]); candidate=base+(1 if edge["relation"]=="inference" else 0); depth[target]=max(depth[target],candidate)
    stable={x:[y for y in order if y in parents[x]] for x in order}; return stable,max(depth.values())

def accepted_sets(support):
    sets=[]
    if support["is_sufficient"] and support["if_minimum"]: sets.append((support["selected_source_ids"],support["support_reason"]))
    for alt in support["alternative_minimum_sets"]:
        if alt["is_sufficient"] and alt["if_minimum"]: sets.append((alt["source_ids"],alt["support_reason"]))
    return sets

def assemble_record(base,side,j,batch,schema,validator_version):
    if base["processing_stage"]!="gpt_screened": raise ContractError("assemble input is not gpt_screened")
    if batch.get("run_id")!=base["dataset_manifest"]["run_id"] or side.get("run_id")!=batch.get("run_id"): raise ContractError("assemble run binding mismatch")
    expected_screening={**batch["screening"],"requires_human_audit":True}
    if base.get("semantic_screening")!=expected_screening: raise ContractError("screened provenance differs from authoritative batch")
    adapter_base=copy.deepcopy(base); adapter_base["processing_stage"]="adapter_candidate"
    adapter_base["semantic_screening"]={"method":None,"model":None,"reasoning_effort":None,"prompt_version":None,"rule_version":batch["screening"]["rule_version"],"screened_at":None,"requires_human_audit":True}
    validate_sidecar(side,adapter_base)
    validate_judgment(j,base,side)
    if j["decision"]!="qualified" or j["requires_human_review"] or j["confidence"]["uncertainty_reasons"]: raise ContractError("judgment is not eligible for silver")
    refs=[p["local_ref"] for p in j["claim_proposals"]]; mapping={ref:f"{base['sample']['sample_id']}:claim:{i}" for i,ref in enumerate(refs)}
    edges=[{"source_node_ids":[mapping[x] for x in e["source_node_refs"]],"target_node_id":mapping[e["target_node_ref"]],"relation":e["relation"]} for e in j["graph_judgment"]["accepted_edges"]]
    order=[mapping[x] for x in refs]; parents,hop=derive_graph(edges,order)
    out=copy.deepcopy(base); out["processing_stage"]="silver"; out["claims"]=[]
    for p in j["claim_proposals"]:
        cid=mapping[p["local_ref"]]; out["claims"].append({"claim_id":cid,"sample_id":out["sample"]["sample_id"],"claim_text":p["claim_text"],"structured_form":None,"claim_kind":"derived","parent_claim_ids":parents[cid],"derivation_operator":p["derivation_operator"],"derivation_rule_version":batch["screening"]["rule_version"],"annotation_status":"silver"})
    supports=sorted(j["support_judgments"],key=lambda x:(refs.index(x["claim_local_ref"]),x["support_ref"])); links=[]
    reason_by_candidate={c["claim_candidate_refs"][0]:c["automatic_match_reason"] for c in side["link_candidates"] if len(c["claim_candidate_refs"])==1}
    proposals={p["local_ref"]:p for p in j["claim_proposals"]}
    for support in supports:
        label=support["label"]
        if label not in {"supported_direct","supported_joint","premise_only"}: continue
        for source_set,_reason in accepted_sets(support):
            relation="direct_entailment" if label=="supported_direct" else "joint_entailment" if label=="supported_joint" else "derivation_premise"
            if relation=="direct_entailment" and len(source_set)!=1: raise ContractError("direct support must have one source")
            if relation=="joint_entailment" and len(source_set)<2: raise ContractError("joint support must have at least two sources")
            origin=proposals[support["claim_local_ref"]]["origin_candidate_refs"]
            auto=next((reason_by_candidate[x] for x in origin if x in reason_by_candidate),None)
            links.append({"link_id":f"{out['sample']['sample_id']}:link:{len(links)}","claim_id":mapping[support["claim_local_ref"]],"source_ids":source_set,"if_minimum":True,"relation":relation,"validation_status":"accepted","automatic_match_reason":auto,"confidence":None,"needs_review":True,"reviewer":f"gpt:{batch['screening']['model']}","review_timestamp":batch["screening"]["screened_at"],"rule_version":batch["screening"]["rule_version"]})
    if not links: raise ContractError("silver requires accepted links")
    out["claim_source_links"]=links; out["reasoning_graph"]={"reasoning_graph_id":f"{out['sample']['sample_id']}:graph:0","sample_id":out["sample"]["sample_id"],"node_ids":order,"edges":edges,"reasoning_hop_count":hop,"graph_type":side["selection"]["final_quota_cell"]["template"],"graph_origin":"derived"}
    out["validation"]={"status":"qualified","errors":{},"warnings":{},"validator_version":validator_version,"validated_at":now()}
    errors=schema_errors(out,schema)
    if errors: raise ContractError("silver HM schema failure: "+"; ".join(errors[:10]))
    check,_=derive_graph(edges,order)
    if any(c["parent_claim_ids"]!=check[c["claim_id"]] for c in out["claims"]): raise ContractError("parent derivation mismatch")
    return out

def load_all_screened(root):
    items=[]
    for path in sorted((root/"gpt_screened").glob("*.jsonl")):items+=read_jsonl(path)
    return indexed(items,"sample.sample_id","screened sample") if items else {}

def assemble_command(args,cfg_path,cfg):
    root=resolve(cfg["paths"]["output_root"],cfg_path); schema=read_json(resolve(cfg["paths"]["hm_schema"],cfg_path)); screened=load_all_screened(root); effective_quotas,amendment_ref=load_quota_policy(root)
    supplied_sidecar_path=Path(args.sidecars).resolve(); sidecars=indexed(read_jsonl(supplied_sidecar_path),"sample_id","sidecar sample")
    eligible=defaultdict(list); rejected=[]; review=[]; errors=[]; seen_judgments={}
    for path in sorted(Path(args.judgment_dir).resolve().rglob("batch_*.json")):
        batch=read_json(path)
        binding=batch.get("input_binding",{})
        candidate_path=Path(binding.get("candidate_file", ""))
        bound_sidecar_path=Path(binding.get("sidecar_file", ""))
        if not candidate_path.is_absolute(): candidate_path=(path.parent/candidate_path).resolve()
        if not bound_sidecar_path.is_absolute(): bound_sidecar_path=(path.parent/bound_sidecar_path).resolve()
        try:
            _,_,verified=verify_batch(batch,candidate_path,bound_sidecar_path,schema)
            if file_digest(bound_sidecar_path)!=file_digest(supplied_sidecar_path): raise ContractError("assemble sidecar differs from batch-bound sidecar")
        except Exception as exc:
            errors.append({"sample_id":None,"batch_file":str(path),"error":f"batch verification failed: {exc}"}); continue
        for j in batch.get("judgments",[]):
            sid=j.get("sample_id")
            if sid in seen_judgments:
                if canon(seen_judgments[sid])==canon(j): continue
                errors.append({"sample_id":sid,"batch_file":str(path),"error":"conflicting judgment repeated across batches"}); continue
            seen_judgments[sid]=j
            if sid not in screened or sid not in sidecars: errors.append({"sample_id":sid,"batch_file":str(path),"error":"missing screened record or sidecar"}); continue
            if j.get("decision")=="rejected": rejected.append({"sample_id":sid,"judgment":j}); continue
            if j.get("decision")=="review_required": review.append({"sample_id":sid,"judgment":j}); continue
            try:
                record=assemble_record(screened[sid],sidecars[sid],j,batch,schema,cfg["versions"]["validator"])
                cell=sidecars[sid]["selection"]["final_quota_cell"]["template"]
                eligible[cell].append((sidecars[sid]["selection"]["pool_rank"],record,j))
            except Exception as exc: errors.append({"sample_id":sid,"batch_file":str(path),"error":str(exc)})
    chosen=[]; overflow=[]; counts={}
    for cell,target in effective_quotas.items():
        ordered=sorted(eligible[cell],key=lambda x:x[0]); selected=ordered[:target]; extra=ordered[target:]
        chosen += [(cell,x[1]) for x in selected]; overflow += [{"sample_id":x[1]["sample"]["sample_id"],"quota_cell":cell,"pool_rank":x[0],"decision":"overflow_qualified"} for x in extra]; counts[cell]=len(selected)
    status="complete" if counts==effective_quotas and len(chosen)==200 else "partial"
    report={"status":status,"selected_count":len(chosen),"counts":counts,"original_targets":QUOTAS,"effective_targets":effective_quotas,"deficits":{c:effective_quotas[c]-counts[c] for c in effective_quotas},"amendment":amendment_ref,"postprocess_error_count":len(errors),"review_required_count":len(review),"rejected_count":len(rejected),"overflow_count":len(overflow)}
    if args.dry_run: print(json.dumps(report,ensure_ascii=False,indent=2)); return
    final=root/"final_silver"; exclusions=root/"exclusions"; manifests=root/"manifests"; final.mkdir(parents=True,exist_ok=True); exclusions.mkdir(exist_ok=True); manifests.mkdir(exist_ok=True)
    for cell in effective_quotas: atomic_jsonl(final/f"{cell}.jsonl",[r for c,r in chosen if c==cell])
    if status=="complete": atomic_jsonl(final/"MuSiQue_final_200_silver.jsonl",[r for _,r in chosen])
    elif (final/"MuSiQue_final_200_silver.jsonl").exists(): raise ContractError("partial run cannot coexist with final_200 output")
    atomic_jsonl(exclusions/"postprocess_errors.jsonl",errors); atomic_jsonl(exclusions/"insufficient_support.jsonl",rejected); atomic_jsonl(exclusions/"review_required.jsonl",review); atomic_jsonl(exclusions/"overflow_qualified.jsonl",overflow)
    write_json(manifests/"postprocess_manifest.json",{**report,"generated_at":now()}); write_json(manifests/"validation_report.json",{"schema_version":"2.1","validated_silver_count":len(chosen),"errors":errors,"generated_at":now()}); write_json(manifests/"gpt_screening_total_manifest.json",report)
    numeric=[{"sample_id":r["sample"]["sample_id"],"quota_cell":c,"labels":sidecars[r["sample"]["sample_id"]]["soft_coverage_labels"]} for c,r in chosen]
    (manifests/"numeric_supplement.md").write_text("# MuSiQue numeric supplement\n\nThis is a coverage-only report; it creates no quota or HM fact field.\n\n```json\n"+json.dumps(numeric,ensure_ascii=False,indent=2)+"\n```\n",encoding="utf-8",newline="\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))

def atomic_jsonl(path,items):
    path.parent.mkdir(parents=True,exist_ok=True); fd,name=tempfile.mkstemp(prefix=".tmp_",suffix=".jsonl",dir=path.parent); os.close(fd); tmp=Path(name)
    try: write_jsonl(tmp,items); os.replace(tmp,path)
    except Exception:
        if tmp.exists():tmp.unlink()
        raise

def ledger_command(args,cfg_path,cfg):
    root=resolve(cfg["paths"]["output_root"],cfg_path); effective_quotas,amendment_ref=load_quota_policy(root); counts={cell:0 for cell in effective_quotas}; ids=set(); errors=[]
    for cell in effective_quotas:
        path=root/"final_silver"/f"{cell}.jsonl"
        if not path.exists():continue
        for record in read_jsonl(path):
            sid=record.get("sample",{}).get("sample_id")
            if sid in ids:errors.append(f"duplicate silver sample {sid}")
            ids.add(sid); counts[cell]+=1
    overflow_path=root/"exclusions"/"overflow_qualified.jsonl"; overflow=len(read_jsonl(overflow_path)) if overflow_path.exists() else 0
    status="complete" if counts==effective_quotas and len(ids)==200 and not errors else "partial" if not errors else "failed"
    print(json.dumps({"status":status,"counts":counts,"original_targets":QUOTAS,"effective_targets":effective_quotas,"amendment":amendment_ref,"total":len(ids),"overflow":overflow,"errors":errors},ensure_ascii=False,indent=2))
    if status=="failed":raise ContractError("ledger validation failed")

def self_check(cfg_path,cfg):
    schema=read_json(resolve(cfg["paths"]["hm_schema"],cfg_path)); base=read_json(resolve(cfg["paths"]["hm_template"],cfg_path))
    # HM stage-condition smoke tests use a compact legal MuSiQue record.
    base["dataset_manifest"].update({"dataset_name":"MuSiQue","release":"v1.0","split":"dev","source_file":"fixture.jsonl","file_sha256":"a"*64,"run_id":"fixture"})
    base["sample"].update({"sample_id":"MuSiQue:v1.0:dev:x","original_sample_id":"x","dataset_name":"MuSiQue","release":"v1.0","split":"dev","question_type":"2hop","question_level":None,"raw_locator":{}})
    base["documents"]=[{"context_index":0,"title":"T","text":"Evidence.","sentences":[],"is_supporting_context":True,"raw_locator":{}}]
    base["sources"]=[{"source_id":"MuSiQue:v1.0:dev:x:source:0","sample_id":"MuSiQue:v1.0:dev:x","context_index":0,"title":"T","entity_qid":None,"paragraph_idx":0,"sent_id":None,"char_start":None,"char_end":None,"text":"Evidence.","granularity":"paragraph","source_origin":"official_gold","raw_locator":{},"locator_status":"valid"}]
    assert not schema_errors(base,schema); bad=copy.deepcopy(base); bad["claims"]=[{"x":1}]; assert schema_errors(bad,schema)
    screened=copy.deepcopy(base); screened["processing_stage"]="gpt_screened"; screened["semantic_screening"].update({"method":"gpt","model":"fixture","reasoning_effort":"medium","prompt_version":"1","screened_at":now()}); assert not schema_errors(screened,schema)
    parents,hop=derive_graph([{"source_node_ids":["a","b"],"target_node_id":"c","relation":"comparison"}],["a","b","c"]); assert parents["c"]==["a","b"] and hop==1
    silver=copy.deepcopy(screened); silver["processing_stage"]="silver"; cid="MuSiQue:v1.0:dev:x:claim:0"
    silver["claims"]=[{"claim_id":cid,"sample_id":silver["sample"]["sample_id"],"claim_text":"Evidence is present.","structured_form":None,"claim_kind":"derived","parent_claim_ids":[],"derivation_operator":"qa_to_statement","derivation_rule_version":"fixture","annotation_status":"silver"}]
    silver["claim_source_links"]=[{"link_id":"MuSiQue:v1.0:dev:x:link:0","claim_id":cid,"source_ids":[silver["sources"][0]["source_id"]],"if_minimum":True,"relation":"direct_entailment","validation_status":"accepted","automatic_match_reason":None,"confidence":None,"needs_review":True,"reviewer":"gpt:fixture","review_timestamp":screened["semantic_screening"]["screened_at"],"rule_version":"fixture"}]
    silver["reasoning_graph"]={"reasoning_graph_id":"MuSiQue:v1.0:dev:x:graph:0","sample_id":silver["sample"]["sample_id"],"node_ids":[cid],"edges":[],"reasoning_hop_count":1,"graph_type":"2hop","graph_origin":"derived"}
    silver["validation"]={"status":"qualified","errors":{},"warnings":{},"validator_version":"fixture","validated_at":now()}
    assert not schema_errors(silver,schema)
    bad_min=copy.deepcopy(silver); bad_min["claim_source_links"][0]["if_minimum"]=False; assert schema_errors(bad_min,schema)
    bad_source=copy.deepcopy(base); bad_source["sources"][0].update({"granularity":"sentence","paragraph_idx":None,"sent_id":0}); assert schema_errors(bad_source,schema)
    print("postprocessor self-check: PASS")

def main():
    parser=argparse.ArgumentParser(description="MuSiQue GPT stage updater, silver assembler, and quota ledger validator")
    parser.add_argument("--config",default=str(Path(__file__).with_name("adapter_config.json"))); parser.add_argument("--self-check",action="store_true")
    sub=parser.add_subparsers(dest="command")
    mark=sub.add_parser("mark-gpt-screened"); mark.add_argument("--batch",required=True); mark.add_argument("--candidate",required=True); mark.add_argument("--sidecars",required=True); mark.add_argument("--dry-run",action="store_true")
    assemble=sub.add_parser("assemble-silver"); assemble.add_argument("--judgment-dir",required=True); assemble.add_argument("--sidecars",required=True); assemble.add_argument("--dry-run",action="store_true")
    sub.add_parser("validate-ledger")
    args=parser.parse_args(); cp=Path(args.config).resolve()
    try:
        cfg=load_config(cp)
        if args.self_check:self_check(cp,cfg)
        elif args.command=="mark-gpt-screened":mark_command(args,cp,cfg)
        elif args.command=="assemble-silver":assemble_command(args,cp,cfg)
        elif args.command=="validate-ledger":ledger_command(args,cp,cfg)
        else:parser.print_help(); return 2
        return 0
    except Exception as exc:print(f"ERROR: {exc}"); return 2
if __name__=="__main__":raise SystemExit(main())
