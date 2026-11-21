"""Read-only release checks using aggregate CSVs, without document or ledger access."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'paper_figures/source_data'
STAGE = ROOT / 'results/research_change/final_statistics_stage_20261012'
METRICS = ['CSR', 'ESS', 'VSSR', 'AA']


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def expected_changes():
    terminal = read(STAGE / 'terminal_union_statistics_20261015/condition_question_macro.csv')
    nodes = read(STAGE / 'paper_node_edge_statistics_20261013/condition_and_stratum_tables.csv')
    changes, seen = [], {}
    for number in range(2, 7):
        for row in read(DATA / f'Table_{number}.csv'):
            if number == 2:
                model, protocol = row['Model / protocol'].split(' / ')
                dataset, condition, kind = '2wiki', 'M', 'node'
                model_id = 'Qwen/Qwen3-8B' if model == 'Qwen3-8B' else 'DeepSeek/deepseek-flash'
                cell = f'{dataset}|{model_id}|M|m3-M@{protocol}|chain'
            else:
                dataset = ('musique' if row.get('Dataset') == 'MuSiQue' else '2wiki') if number == 5 else ('musique' if number == 6 else '2wiki')
                condition, kind, protocol = row.get('Condition', 'M'), 'terminal', '1.0.4'
                cell = ''
            for metric in METRICS:
                key = (kind, dataset, condition, protocol, cell, metric)
                new = Decimal(row[metric])
                if key in seen:
                    if seen[key] != new:
                        raise ValueError(f'Repeated value differs: {key}')
                    continue
                seen[key] = new
                if kind == 'node':
                    matches = [r for r in nodes if r['kind'] == 'node' and r['view'] == 'candidate_sample_corrected' and r['cell_id'] == cell and r['phase'] == 'all' and r['question_stratum'] == 'ALL' and r['metric'] == metric]
                    field = 'question_macro_mean'
                    source = 'paper_node_edge_statistics_20261013/condition_and_stratum_tables.csv'
                else:
                    matches = [r for r in terminal if r['dataset'] == dataset and r['condition'] == condition and r['view'] == 'sample_replaced' and r['metric'] == metric]
                    field = 'mean'
                    source = 'terminal_union_statistics_20261015/condition_question_macro.csv'
                if len(matches) != 1:
                    raise ValueError(f'Ambiguous historical aggregate: {key}')
                old = (Decimal(matches[0][field])*100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                if old != new:
                    changes.append({'kind': kind, 'dataset': dataset, 'condition': condition,
                                    'protocol': protocol, 'metric': metric, 'old_percent': str(old),
                                    'new_percent': str(new), 'source': source,
                                    'released_table': f'Table_{number}.csv',
                                    'basis': 'author_revised_aggregate; no record-level correction map supplied'})
    return changes


def main():
    manifest = json.loads((ROOT / 'paper_figures/figure_data_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        p = (ROOT / item['path']).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file():
            raise ValueError(f'Missing/outside input: {p}')
        if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'Changed input: {p}')
    mirror, expected = read(DATA / 'figure_source_data.csv'), []
    for number in range(2, 7):
        rows = read(DATA / f'Table_{number}.csv')
        if len(rows) != (2 if number == 5 else 3):
            raise ValueError('Unexpected display rows')
        for j, row in enumerate(rows):
            label = next(iter(row.values())).replace(' / ', ' ')
            if number == 2:
                label = ['DeepSeek 1.0.4', 'DeepSeek earlier', 'Qwen3-8B'][j]
            for metric in METRICS:
                value = Decimal(row[metric])
                if not 0 <= value <= 100:
                    raise ValueError('Percentage outside bounds')
                expected.append((str(number), label, metric, value))
    actual = [(r['figure'], r['series'], r['metric'], Decimal(r['value_percent'])) for r in mirror]
    if sorted(actual) != sorted(expected):
        raise ValueError('Long-form mirror differs from authoritative tables')
    if any(r['interval'] != 'Not supplied for revised estimates' for r in mirror):
        raise ValueError('Unexpected uncertainty assertion')
    for row in read(DATA / 'edge_comparison.csv'):
        n, d = Decimal(row['numerator']), Decimal(row['denominator'])
        if not 0 <= n <= d:
            raise ValueError('Invalid edge counts')
        if d == 0:
            if row['percent']:
                raise ValueError('Undefined rate must be empty')
        elif abs(Decimal(row['percent']) - n/d*100) > Decimal('.000001'):
            raise ValueError('Edge rate differs from counts')
    for row in read(DATA / 'audit_coverage.csv'):
        if int(row['records']) != int(row['reviewed_or_reused']) + int(row['candidate_only']):
            raise ValueError('Coverage counts do not reconcile')
    changes = expected_changes()
    if read(Path(__file__).parent / 'value_changes.csv') != changes:
        raise ValueError('Numeric revision ledger differs from historical/released aggregates')
    print(json.dumps({'status': 'PASS', 'display_points': len(expected), 'hashed_files': len(manifest['files']),
                      'numeric_changes': len(changes), 'document_dependency': False,
                      'record_level_recomputation': False}, indent=2))


if __name__ == '__main__':
    main()
