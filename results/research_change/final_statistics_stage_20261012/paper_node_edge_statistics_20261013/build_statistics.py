# English publication adaptation of a historical script; no experiment or adjudication was rerun.
"""Read-only sources; reproducible exploratory node/edge analysis. See ANALYSIS_SPEC.md."""
from pathlib import Path
import csv, gzip, hashlib, json, sys, subprocess, collections, copy, platform
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROJECT = ROOT.parent
STAGE = HERE.parent
NS = STAGE / 'remaining_node_sample_20261013'
ES = STAGE / 'remaining_edge_sample_20261012'
INPUTS = {}

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def track(p):
    p = Path(p)
    INPUTS[str(p)] = sha(p)
    return p

def readjson(p):
    return json.loads(track(p).read_text(encoding='utf-8-sig'))

def readlines(p):
    p = track(p)
    op = gzip.open if p.suffix == '.gz' else open
    with op(p, 'rt', encoding='utf-8-sig') as f:
        return [json.loads(s) for s in f if s.strip()]

def readcsv(p):
    with track(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def writejson(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def writelines(name, rows):
    with (HERE / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

def writecsv(name, rows):
    if not rows:
        return
    keys = list(dict.fromkeys((k for r in rows for k in r)))
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()})

def nk(x):
    return (x['run_id'], x['node_id'], x['truth_claim_id'])

def ek(x):
    return (x['run_id'], x['dependency_id'], x.get('truth_claim_id', x.get('truth_claim_ids', [None])[0]))

def validate():
    sys.path.insert(0, str(PROJECT / 'src'))
    from agent_lab.m2_contracts import NodeJudgment, EdgeJudgment
    import pydantic
    counts = collections.Counter()
    fail = []
    metadata_counts = collections.Counter()
    for name, model in [('node_analysis_ledger.jsonl', NodeJudgment), ('edge_analysis_ledger.jsonl', EdgeJudgment)]:
        for line in (HERE / name).read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            for field in ['original_candidate', 'exact_judgment', 'sample_analysis_judgment']:
                j = r.get(field)
                if j is not None:
                    try:
                        extras = set(j) - set(model.model_fields)
                        allowed = {'batch_id', 'checkpoint_sha256', 'mechanical_rule_version', 'model_version', 'observation_key', 'observation_version', 'rule_version', 'frozen_empty_candidate_sha256'} if model is NodeJudgment else set()
                        assert extras <= allowed, f'Unknown fields: {extras - allowed}'
                        for k in extras:
                            metadata_counts[k] += 1
                        model.model_validate({k: v for k, v in j.items() if k in model.model_fields})
                        counts[name + ':' + field] += 1
                    except Exception as e:
                        fail.append({'scope_id': r['scope_id'], 'field': field, 'error': str(e)})
    writejson('m2_validation.json', {'python': platform.python_version(), 'pydantic': pydantic.__version__, 'validated': dict(counts), 'source_envelope_metadata_preserved_separately': dict(metadata_counts), 'failures': fail})
    if fail:
        raise RuntimeError(f'{len(fail)} M2 errors; see m2_validation.json')
    print('M2 validation passed', dict(counts))

def normalized_human(f, c):
    h = f['human_review']
    j = copy.deepcopy(c)
    for k in ['claim_presence', 'source_marker_status', 'runtime_source_ids', 'support_fine', 'unsupported_spans', 'qualification_change', 'disposition', 'review_status', 'review_reason_codes', 'rationale']:
        j[k] = h[k]
    v = h['content_truth']
    j['content_truth'] = 'true' if v is True else 'false' if v is False else v
    ids = h['aligned_runtime_claim_ids']
    typ = h['alignment_type']
    truths = [] if typ == 'none' else c['alignment']['truth_claim_ids'] if typ == c['alignment']['alignment_type'] else [f['truth_claim_id']]
    j['alignment'] = {'alignment_id': 'analysis_' + f['sample_id'], 'alignment_type': typ, 'truth_claim_ids': truths, 'runtime_claim_ids': ids}
    eq = j['claim_presence'] == 'present_equivalent'
    j['semantic_equivalence'] = eq
    j['interpretable'] = j['claim_presence'] != 'uninterpretable'
    if not eq:
        j.update(exact_set_survived=None, source_change_status='not_applicable')
    elif j['source_marker_status'] == 'identifiable':
        exact = set(j['canonical_source_ids']) == set(j['runtime_source_ids'])
        j.update(exact_set_survived=exact, source_change_status='unchanged' if exact else 'substituted_valid' if j['support_fine'] == 'fully_supported' else 'substituted_invalid')
    elif j['source_marker_status'] == 'absent':
        j.update(exact_set_survived=False, source_change_status='dropped')
    elif j['source_marker_status'] == 'unidentifiable':
        j.update(exact_set_survived=False, source_change_status='unidentifiable')
    else:
        raise ValueError('Equivalent human claim lacks source applicability')
    j.update(judgment_id='analysis_' + f['sample_id'], origin='manual', is_final=False, annotator_id=h['reviewer_id'], created_at=h['reviewed_at'])
    return j

def features(j, kind):
    d = {'disposition_' + j['disposition']: 1, 'review_unresolved': int(j['review_status'] == 'needs_review')}
    assert j['review_status'] == 'decided', 'Review denominator needs explicit resolution'
    if kind == 'node':
        eq = j['claim_presence'] == 'present_equivalent'
        d.update(CSR=int(eq), ESS=int(j['exact_set_survived'] is True), VSSR=int(j['source_change_status'] == 'substituted_valid'), AA=int(eq and j['support_fine'] == 'fully_supported'))
        cat = 'ClaimDropped' if not eq else 'SourceMissing' if j['source_marker_status'] in ['absent', 'unidentifiable'] else 'FullSupport' if j['support_fine'] == 'fully_supported' else 'PartialSupport' if j['support_fine'] == 'partially_supported' else 'NotSupport' if j['support_fine'] in ['contradicted', 'insufficient'] else None
        assert cat is not None
        d['outcome_' + cat] = 1
        d['presence_' + j['claim_presence']] = 1
        d['source_change_' + j['source_change_status']] = 1
        d['content_truth_' + j['content_truth']] = 1
        d['qualification_any'] = int(bool(j['qualification_change']))
    else:
        ce = j['claim_event']
        se = j['source_events']
        exact_applicable = ce in ['claim_retained_equivalent', 'claim_rewritten_non_equivalent', 'claim_split', 'claim_merged']
        d.update(ClaimApplicable=int(ce != 'not_applicable'), ClaimRetained=int(ce == 'claim_retained_equivalent'), ExactApplicable=int(exact_applicable), SourceExact=int('source_set_retained_exact' in se), SourceExactApplicable=int(exact_applicable and 'source_set_retained_exact' in se), SourceExactOutsideApplicable=int(not exact_applicable and 'source_set_retained_exact' in se), SubstitutionApplicable=int(bool(set(se) & {'source_substituted_valid', 'source_substituted_invalid'})), SubstitutionValid=int('source_substituted_valid' in se))
        d['claim_event_' + ce] = 1
        d['support_event_' + j['support_event']] = 1
        for s in set(se):
            d['source_event_' + s] = 1
    return d

def main():
    import numpy as np
    frozen = readjson(ROOT / 'frozen_v1/manifest.json')
    bad = []
    for rel, expected in frozen['files_sha256'].items():
        p = ROOT / 'frozen_v1' / rel
        if not p.exists() or sha(p) != expected:
            bad.append(rel)
    assert not bad, bad
    logs = {}
    for p in [NS / 'verify_sample.py', STAGE / 'edge_population_final_report_20261013/verify_edge_population.py']:
        z = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, encoding='utf-8', errors='replace')
        logs[p.name + str(p.parent.name)] = {'exit_code': z.returncode, 'stdout': z.stdout, 'stderr': z.stderr}
        assert z.returncode == 0, z.stderr
    form = readjson(NS / 'human_review_form_633.json')
    assert sha(NS / 'human_review_form_633.json') == '342d58c5fd8f2737924a1366a2458afe6424ec1c7253efc3c37f189289c83851'
    oldnode = readjson(NS / 'weighted_estimates_after_node_review.json')
    assert oldnode['form_sha256'] == sha(NS / 'human_review_form_633.json')
    oldedge = readjson(STAGE / 'edge_population_final_report_20261013/edge_population_estimates.json')
    questions = {x['question_id']: x for x in readlines(ROOT / 'frozen_v1/selected_questions.jsonl')}
    op = track(ROOT / 'frozen_v1/selected_observations.jsonl.gz')
    obs = {}
    union = []
    with gzip.open(op, 'rt', encoding='utf-8') as stream:
        for line in stream:
            x = json.loads(line)
            key = (x['run_id'], x['question_id'])
            assert key not in obs
            m = {k: x[k] for k in ['observation_key', 'run_id', 'question_id', 'dataset', 'model', 'condition', 'topology', 'replicate_index', 'prompt_ref', 'prompt_set_hash', 'observation_version', 'requires_explicit_hop_union']}
            m['question_stratum'] = '|'.join(map(str, questions[x['question_id']]['stratum']))
            m['cell_id'] = '|'.join((m[k] for k in ['dataset', 'model', 'condition', 'prompt_ref', 'topology']))
            m['node_hops'] = {n['node_id']: n['communication_hop'] for n in x['runtime_nodes']}
            m['edge_hops'] = {e['dependency_id']: m['node_hops'][e['child_node_id']] for e in x['dependencies']}
            m['n_truth'] = len(x['truth_view']['truth_claims'])
            m['n_nodes'] = len(x['runtime_nodes'])
            m['n_dependencies'] = len(x['dependencies'])
            m['n_node_scopes'] = m['n_truth'] * m['n_nodes']
            m['n_edge_scopes'] = m['n_truth'] * m['n_dependencies']
            obs[key] = m
            maxhop = max(m['node_hops'].values())
            terminal = [n for n, h in m['node_hops'].items() if h == maxhop]
            for hop in sorted(set(m['node_hops'].values())):
                nodes = [n for n, h in m['node_hops'].items() if h == hop]
                union.append({**{k: m[k] for k in ['observation_key', 'run_id', 'question_id', 'dataset', 'model', 'condition', 'prompt_ref', 'topology', 'replicate_index', 'question_stratum']}, 'communication_hop': hop, 'scope_node_ids': nodes, 'n_nodes': len(nodes), 'n_truth_claims': m['n_truth'], 'is_terminal_hop': hop == maxhop, 'requires_multi_node_union': len(nodes) > 1, 'union_judgments_available': 0})
    assert len(obs) == 680 and sum((m['n_node_scopes'] for m in obs.values())) == 7098 and (sum((m['n_edge_scopes'] for m in obs.values())) == 2444)
    writecsv('union_scope_inventory.csv', union)
    nc = {}
    for p in sorted((ROOT / 'reviews').glob('session_*/batch_*/node_candidates.jsonl')):
        for raw in readlines(p):
            j = raw.get('judgment', raw)
            assert nk(j) not in nc
            nc[nk(j)] = j
    ne = {nk(j): j for j in readlines(ROOT / 'final_node_audit_20261011/node_judgments_adjudicated_final.jsonl')}
    nf = {nk(f): f for f in form}
    npop = {nk(x): x for x in readcsv(NS / 'population_allocation_6329.csv')}
    assert len(nc) == 7098 and len(ne) == 769 and (len(nf) == 633) and set(ne).isdisjoint(npop) and (set(ne) | set(npop) == set(nc)) and (set(nf) <= set(npop))
    ec = {}
    for raw in readlines(STAGE / 'edge_candidate_sensitivity_20261013/candidate_view_remaining_1885.jsonl'):
        j = raw['judgment']
        assert ek(j) not in ec
        ec[ek(j)] = j
    ee = {ek(j): j for j in readlines(ROOT / 'final_edge_audit_20261012/edge_judgments_adjudicated_559.jsonl')}
    ef = {ek(j): j for j in readlines(STAGE / 'final_sample_edge_audit_20261013/edge_judgments_adjudicated_sample_189.jsonl')}
    eq = {ek(q): q for q in readjson(ES / 'sample_queue_189.json')}
    epop = {ek(x): x for x in readcsv(ES / 'population_allocation_1885.csv')}
    coverage = {ek(x): x for x in readcsv(STAGE / 'edge_scope_coverage_2444.csv')}
    assert len(ec) == 1885 and len(ee) == 559 and (len(ef) == 189) and (set(ef) == set(eq)) and set(ee).isdisjoint(ec) and (set(ee) | set(ec) == set(coverage))
    ledgers = {}
    for kind, candidates, exact, sampled, pop in [('node', nc, ne, nf, npop), ('edge', ec, ee, ef, epop)]:
        rows = []
        for key in sorted(set(candidates) | set(exact)):
            c = candidates.get(key)
            e = exact.get(key)
            s = sampled.get(key)
            if kind == 'node' and s:
                human = normalized_human(s, c)
                queue = s
            elif s:
                human = s
                queue = eq[key]
            else:
                human = None
                queue = None
            j = e or c
            m = obs[j['run_id'], j['question_id']]
            hop = m['node_hops'][j['node_id']] if kind == 'node' else m['edge_hops'][j['dependency_id']]
            sampling = queue['sampling'] if queue else None
            r = {k: m[k] for k in ['cell_id', 'observation_key', 'run_id', 'question_id', 'dataset', 'model', 'condition', 'topology', 'replicate_index', 'prompt_ref', 'prompt_set_hash', 'observation_version', 'question_stratum']}
            r.update(scope_id='|'.join(key), scope_kind=kind, communication_hop=hop, truth_claim_id=key[2], original_candidate=c, exact_judgment=e, sample_analysis_judgment=human, audit_layer='prior_exact' if e else 'sample_human' if human else 'not_individually_reviewed', expansion_weight=1 if e else sampling['expansion_weight'] if sampling else 0, sampling_stratum=sampling['stratum'] if sampling else pop[key].get('sampling_stratum', '') if key in pop else '', sample_id=queue.get('sample_id') if queue else None)
            rows.append(r)
        ledgers[kind] = rows
        writelines(kind + '_analysis_ledger.jsonl', rows)
    validation = subprocess.run([str(PROJECT / '.venv/Scripts/python.exe'), str(Path(__file__).resolve()), '--validate'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert validation.returncode == 0, validation.stdout + validation.stderr
    names = {}
    for kind, rows in ledgers.items():
        names[kind] = sorted(set().union(*(features(j, kind).keys() for r in rows for j in [r['exact_judgment'] or r['original_candidate'], r['sample_analysis_judgment']] if j)))
        extras = ['CSR', 'ESS', 'VSSR', 'AA', 'review_unresolved'] + [f'outcome_{s}' for s in ['FullSupport', 'PartialSupport', 'NotSupport', 'SourceMissing', 'ClaimDropped']] if kind == 'node' else ['ClaimApplicable', 'ClaimRetained', 'ExactApplicable', 'SourceExact', 'SubstitutionApplicable', 'SubstitutionValid', 'review_unresolved']
        names[kind] = sorted(set(names[kind] + extras))
    views = ['audit_HT', 'candidate_baseline', 'candidate_sample_corrected', 'audit_difference']
    ag = {}
    units = {}
    global_counts = {}
    global_layer = {}
    eventrows = []
    for kind, rows in ledgers.items():
        nm = names[kind]
        dim = len(nm)

        def vec(j):
            f = features(j, kind)
            return np.array([f.get(n, 0) for n in nm], float)
        for r in rows:
            ok = (r['run_id'], r['question_id'])
            phases = ['all', f"hop_{r['communication_hop']}"]
            e, h, c = (r['exact_judgment'], r['sample_analysis_judgment'], r['original_candidate'])
            selected = [(e or h, r['expansion_weight']), (e or c, 1), (e or h or c, 1)]
            vals = [(vec(j) * w if j else np.zeros(dim), w if j else 0.0) for j, w in selected]
            difference = vec(e or c) + (r['expansion_weight'] * (vec(h) - vec(c)) if h else 0)
            vals.append((difference, 1.0))
            for phase in phases:
                u = (kind, *ok, phase)
                units[u] = units.get(u, 0) + 1
                for view, (v, w) in zip(views, vals):
                    a = ag.setdefault((view, *u), {'sum': np.zeros(dim), 'weight': 0.0, 'n_exact': 0, 'n_sample': 0, 'n_unreviewed': 0})
                    a['n_exact'] += int(bool(e))
                    a['n_sample'] += int(bool(h))
                    a['n_unreviewed'] += int(not (e or h))
                    a['sum'] += v
                    a['weight'] += w
            for view, (v, w) in zip(views, vals):
                arr = global_counts.setdefault((kind, view), np.zeros(dim))
                arr += v
            if e:
                layer = 'prior_exact'
                j = e
                w = 1
            elif h:
                layer = 'sample_observed'
                j = h
                w = 1
            else:
                continue
            global_layer.setdefault((kind, layer), np.zeros(dim))[:] += vec(j) * w
            if h:
                global_layer.setdefault((kind, 'remaining_estimated'), np.zeros(dim))[:] += vec(h) * r['expansion_weight']
        total = len(rows)
        for view in views:
            for n, v in zip(nm, global_counts[kind, view]):
                eventrows.append({'kind': kind, 'view': view, 'metric': n, 'estimated_count': float(v), 'scope_denominator': total, 'scope_rate': float(v / total)})
        for layer in ['prior_exact', 'sample_observed', 'remaining_estimated']:
            for n, v in zip(nm, global_layer[kind, layer]):
                eventrows.append({'kind': kind, 'view': layer, 'metric': n, 'estimated_count': float(v), 'scope_denominator': {'node': {'prior_exact': 769, 'sample_observed': 633, 'remaining_estimated': 6329}, 'edge': {'prior_exact': 559, 'sample_observed': 189, 'remaining_estimated': 1885}}[kind][layer]})
    writecsv('scope_global_metrics.csv', eventrows)
    for kind, expected in [('node', oldnode['all_node_observed_plus_estimated_counts']), ('edge', oldedge['combined_exact_plus_estimated_2444_disposition'])]:
        for k, v in expected.items():
            assert abs(global_counts[kind, 'audit_HT'][names[kind].index('disposition_' + k)] - v) < 1e-07
    obsrows = []
    qacc = {}
    domain = {}
    denoms = []
    for key, a in ag.items():
        view, kind, run, q, phase = key
        m = obs[run, q]
        den = units[kind, run, q, phase]
        base = {k: m[k] for k in ['cell_id', 'observation_key', 'run_id', 'question_id', 'dataset', 'model', 'condition', 'prompt_ref', 'topology', 'replicate_index', 'question_stratum']}
        obsrows.append({**base, 'kind': kind, 'view': view, 'phase': phase, 'raw_scope_n': den, 'represented_scope_weight': a['weight'], 'n_exact': a['n_exact'], 'n_sample': a['n_sample'], 'n_unreviewed': a['n_unreviewed'], **{n: float(v / den) for n, v in zip(names[kind], a['sum'])}})
        qk = (view, kind, m['cell_id'], q, phase)
        qa = qacc.setdefault(qk, {'values': [], 'replicates': [], 'scope_n': 0, 'weights': 0.0, 'n_sample': 0, 'n_exact': 0})
        qa['values'].append(a['sum'] / den)
        qa['replicates'].append(m['replicate_index'])
        qa['scope_n'] += den
        qa['weights'] += a['weight']
        qa['n_sample'] += a['n_sample']
        qa['n_exact'] += a['n_exact']
        for st in [m['question_stratum'], 'ALL']:
            dk = (view, kind, m['cell_id'], phase, st)
            da = domain.setdefault(dk, {'sum': np.zeros(len(names[kind])), 'weight': 0.0, 'scope_n': 0, 'n_obs': 0, 'questions': set(), 'n_exact': 0, 'n_sample': 0})
            da['sum'] += a['sum']
            da['weight'] += a['weight']
            da['scope_n'] += den
            da['n_obs'] += 1
            da['questions'].add(q)
            da['n_exact'] += a['n_exact']
            da['n_sample'] += a['n_sample']
    writecsv('observation_metrics.csv', obsrows)
    qvalues = {}
    qrows = []
    for k, a in qacc.items():
        view, kind, cell, q, phase = k
        expected = [1] if 'Qwen/' in cell else [1, 2]
        assert sorted(a['replicates']) == expected, (k, a['replicates'])
        v = np.mean(a['values'], axis=0)
        qvalues[k] = v
        qrows.append({'kind': kind, 'view': view, 'cell_id': cell, 'question_id': q, 'phase': phase, 'question_stratum': '|'.join(map(str, questions[q]['stratum'])), 'replicate_n': len(a['replicates']), 'raw_scope_n': a['scope_n'], 'represented_scope_weight': a['weights'], 'n_exact': a['n_exact'], 'n_sample': a['n_sample'], **{n: float(vv) for n, vv in zip(names[kind], v)}})
    writecsv('question_metrics.csv', qrows)
    rng = np.random.default_rng(20261013)
    cache = {}

    def boot_idx(qs):
        qs = tuple(qs)
        if qs not in cache:
            strata = collections.defaultdict(list)
            for i, q in enumerate(qs):
                strata[tuple(questions[q]['stratum'])].append(i)
            cache[qs] = np.concatenate([rng.choice(idx, size=(5000, len(idx)), replace=True) for st, idx in sorted(strata.items())], axis=1)
        return cache[qs]
    summaries = []
    for dk, a in sorted(domain.items()):
        view, kind, cell, phase, st = dk
        qs = sorted(a['questions'])
        mat = np.stack([qvalues[view, kind, cell, q, phase] for q in qs])
        mean = mat.mean(axis=0)
        boot = mat[boot_idx(qs)].mean(axis=1)
        lo, hi = np.quantile(boot, [0.025, 0.975], axis=0)
        base = {'kind': kind, 'view': view, 'cell_id': cell, 'phase': phase, 'question_stratum': st, 'question_n': len(qs), 'observation_n': a['n_obs'], 'scope_n': a['scope_n'], 'represented_scope_weight': a['weight'], 'n_exact': a['n_exact'], 'n_sample': a['n_sample'], 'interval_type': 'fixed_audit_weights_question_bootstrap_descriptive'}
        for i, n in enumerate(names[kind]):
            summaries.append({**base, 'metric': n, 'estimated_count': float(a['sum'][i]), 'scope_rate': float(a['sum'][i] / a['scope_n']), 'question_macro_mean': float(mean[i]), 'bootstrap_lower': float(lo[i]), 'bootstrap_upper': float(hi[i]), 'individual_question_estimates_outside_0_1': int(((mat[:, i] < -1e-09) | (mat[:, i] > 1 + 1e-09)).sum())})
        if view == 'audit_HT':
            denoms.append(base)
        if kind == 'edge':
            for label, num, de in [('EdgeClaimRetention', 'ClaimRetained', 'ClaimApplicable'), ('EdgeExactSourceRetention', 'SourceExactApplicable', 'ExactApplicable'), ('EdgeValidSubstitution', 'SubstitutionValid', 'SubstitutionApplicable')]:
                ni, di = (names[kind].index(num), names[kind].index(de))
                d = a['sum'][di]
                summaries.append({**base, 'metric': label, 'estimated_count': float(a['sum'][ni]), 'applicable_denominator_estimate': float(d), 'applicable_rate': float(a['sum'][ni] / d) if d else None, 'status': 'computed' if d else 'not_applicable'})
    writecsv('condition_and_stratum_tables.csv', summaries)
    writecsv('denominator_ledger.csv', denoms)
    pairs = []
    cells = sorted({m['cell_id'] for m in obs.values()})
    for dataset in ['2wiki', 'musique']:
        lookup = {m['condition']: m['cell_id'] for m in obs.values() if m['dataset'] == dataset and m['model'].startswith('DeepSeek') and m['prompt_ref'].endswith('@1.0.4') and (m['topology'] == 'chain')}
        for other in ['B0', 'B1', 'A1', 'A2']:
            if other in lookup:
                pairs.append((dataset, 'primary_descriptive', lookup['M'], lookup[other], 'M-' + other))
    ds = next((c for c in cells if '2wiki|DeepSeek' in c and '|m3-M@1.0.1c-r2|chain' in c))
    qw = next((c for c in cells if 'Qwen/' in c and c.endswith('|chain')))
    pairs.append(('2wiki', 'model_protocol_descriptive', qw, ds, 'Qwen_chain-DeepSeek_legacy_chain'))
    contrast = []
    for dataset, role, left, right, label in pairs:
        for kind in ['node', 'edge']:
            metrics = ['CSR', 'ESS', 'VSSR', 'AA'] if kind == 'node' else ['ClaimApplicable', 'ClaimRetained', 'SourceExact', 'SubstitutionValid']
            for view in views:
                qs = sorted((q for q in questions if (view, kind, left, q, 'all') in qvalues and (view, kind, right, q, 'all') in qvalues))
                if not qs:
                    contrast.append({'dataset': dataset, 'role': role, 'kind': kind, 'view': view, 'comparison': label, 'left_cell': left, 'right_cell': right, 'status': 'not_applicable_no_edge_in_baseline', 'question_n': 0})
                    continue
                for st in ['ALL'] + sorted({'|'.join(map(str, questions[q]['stratum'])) for q in qs}):
                    sub = [q for q in qs if st == 'ALL' or '|'.join(map(str, questions[q]['stratum'])) == st]
                    mat = np.stack([qvalues[view, kind, left, q, 'all'] - qvalues[view, kind, right, q, 'all'] for q in sub])
                    mean = mat.mean(axis=0)
                    lo, hi = np.quantile(mat[boot_idx(sub)].mean(axis=1), [0.025, 0.975], axis=0)
                    for n in metrics:
                        i = names[kind].index(n)
                        contrast.append({'dataset': dataset, 'role': role, 'kind': kind, 'view': view, 'comparison': label, 'left_cell': left, 'right_cell': right, 'question_stratum': st, 'question_n': len(sub), 'metric': n, 'difference': float(mean[i]), 'bootstrap_lower': float(lo[i]), 'bootstrap_upper': float(hi[i]), 'status': 'computed', 'interval_type': 'fixed_audit_weights_question_bootstrap_descriptive'})
    writecsv('paired_condition_differences.csv', contrast)
    agree = collections.defaultdict(lambda: collections.Counter())
    diff = []
    confusion = collections.Counter()
    for r in ledgers['node']:
        if not r['sample_analysis_judgment']:
            continue
        c, h = (r['original_candidate'], r['sample_analysis_judgment'])
        w = r['expansion_weight']
        comp = {n: c[n] == h[n] for n in ['disposition', 'claim_presence', 'source_marker_status', 'support_fine', 'content_truth']}
        comp['alignment'] = c['alignment']['alignment_type'] == h['alignment']['alignment_type'] and set(c['alignment']['runtime_claim_ids']) == set(h['alignment']['runtime_claim_ids'])
        comp['runtime_source_ids'] = set(c['runtime_source_ids']) == set(h['runtime_source_ids'])
        comp['all_primary_fields'] = all(comp.values())
        for n, yes in comp.items():
            agree[n]['sample_equal'] += yes
            agree[n]['weighted_equal'] += w * yes
        confusion[c['disposition'], h['disposition']] += 1
        if not comp['all_primary_fields']:
            f = nf[nk(h)]
            diff.append({'review_order': f['review_order'], 'sample_id': f['sample_id'], 'scope_id': r['scope_id'], 'changed_fields': [n for n, v in comp.items() if not v and n != 'all_primary_fields'], 'candidate_disposition': c['disposition'], 'human_disposition': h['disposition'], 'human_rationale': h['rationale']})
    ar = [{'field': n, 'equal_n': v['sample_equal'], 'sample_n': 633, 'sample_agreement': v['sample_equal'] / 633, 'weighted_agreement': v['weighted_equal'] / 6329} for n, v in sorted(agree.items())]
    assert next((r for r in ar if r['field'] == 'all_primary_fields'))['equal_n'] == 627
    assert next((r for r in ar if r['field'] == 'disposition'))['equal_n'] == 628
    writecsv('node_candidate_agreement.csv', ar)
    writecsv('node_candidate_disagreements.csv', sorted(diff, key=lambda x: x['review_order']))
    writecsv('node_candidate_confusion.csv', [{'candidate_disposition': a, 'human_disposition': b, 'n': v} for (a, b), v in sorted(confusion.items())])
    bounds = []
    for kind, rows in ledgers.items():
        for metric in ['CSR', 'ESS', 'VSSR', 'AA'] if kind == 'node' else ['ClaimApplicable', 'ClaimRetained', 'SourceExact', 'SubstitutionValid']:
            known = sum((features(r['exact_judgment'] or r['sample_analysis_judgment'], kind).get(metric, 0) for r in rows if r['exact_judgment'] or r['sample_analysis_judgment']))
            unknown = sum((not (r['exact_judgment'] or r['sample_analysis_judgment']) for r in rows))
            bounds.append({'kind': kind, 'metric': metric, 'known_positive': known, 'individually_reviewed_n': len(rows) - unknown, 'unreviewed_n': unknown, 'scope_n': len(rows), 'worst_case_lower': known / len(rows), 'worst_case_upper': (known + unknown) / len(rows), 'meaning': 'identification_bound_without_candidate_validity_assumption_not_CI'})
    writecsv('unreviewed_worst_case_bounds.csv', bounds)
    metadata = []
    for cell in cells:
        mm = [m for m in obs.values() if m['cell_id'] == cell]
        metadata.append({'cell_id': cell, 'question_n': len({m['question_id'] for m in mm}), 'observation_n': len(mm), 'replicate_indices': sorted({m['replicate_index'] for m in mm}), 'node_scope_n': sum((m['n_node_scopes'] for m in mm)), 'edge_scope_n': sum((m['n_edge_scopes'] for m in mm)), 'multi_node_union_observation_n': sum((m['requires_explicit_hop_union'] for m in mm))})
    writecsv('panel_cells.csv', metadata)
    checks = {'status': 'passed', 'frozen_files_checked': len(frozen['files_sha256']), 'source_verifiers': logs, 'node_scope_n': 7098, 'edge_scope_n': 2444, 'question_n': 60, 'observation_n': 680, 'node_sample_n': 633, 'edge_sample_n': 189, 'node_primary_distribution_reproduced': True, 'edge_primary_distribution_reproduced': True, 'node_candidate_agreement_reproduced': True, 'all_question_replicate_identities_verified': True, 'sample_form_sha256': sha(NS / 'human_review_form_633.json'), 'bootstrap_seed': 20261013, 'bootstrap_replicates': 5000, 'python': platform.python_version(), 'numpy': np.__version__}
    writejson('verification.json', checks)
    writejson('analysis_summary.json', {'cells': metadata, 'feature_names': names, 'global_metrics': eventrows, 'node_agreement': ar, 'union_inventory': {'hop_truth_scopes': sum((r['n_truth_claims'] for r in union)), 'terminal_truth_scopes': sum((r['n_truth_claims'] for r in union if r['is_terminal_hop'])), 'multi_node_hop_truth_scopes': sum((r['n_truth_claims'] for r in union if r['requires_multi_node_union'])), 'multi_node_terminal_truth_scopes': sum((r['n_truth_claims'] for r in union if r['is_terminal_hop'] and r['requires_multi_node_union']))}})
    for p in [HERE / 'ANALYSIS_SPEC.md', Path(__file__).resolve(), PROJECT / 'src/agent_lab/m2_contracts.py', PROJECT / 'src/agent_lab/m2.py', ROOT / 'RULES_FROZEN.md', ROOT / 'ANALYSIS_AND_QUALITY_PLAN.md', Path('source_archive/manuscript/original_paper_work_plan.md')]:
        track(p)
    writejson('manifest.json', {'analysis_version': 'exploratory-node-edge-paper-1.0', 'input_sha256': INPUTS, 'output_sha256': {p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name != 'manifest.json'}, 'rounding': 'display estimated counts and percentages to 2 decimal places; CSVs preserve float precision', 'bootstrap': '5000 stratified question resamples, fixed audit weights; descriptive only'})
    print(json.dumps({'status': 'complete', 'cells': len(cells), 'condition_rows': len(summaries), 'contrast_rows': len(contrast), 'output': str(HERE)}, ensure_ascii=False))
if __name__ == '__main__':
    if '--validate' in sys.argv:
        validate()
    else:
        main()
