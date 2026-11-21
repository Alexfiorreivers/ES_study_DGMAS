"""Offline runtime checks. No network, model calls, or writes to source data."""
import os,sys,json,importlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
os.chdir(ROOT)
from agent_lab.runtime import load_config
from agent_lab.m3_prompts import resolve_prompt_set
from agent_lab.m3_execution import validate_condition_contract,validate_condition_matrix
for p in (ROOT/'src/agent_lab').rglob('*.py'):
    rel=p.relative_to(ROOT/'src').with_suffix('')
    importlib.import_module('.'.join(rel.parts[:-1] if rel.name=='__init__' else rel.parts))
configs=[]
for p in sorted((ROOT/'configs/examples').glob('*_mock.yaml')):
    config=load_config(p)
    assert config.provider.kind=='lineage_replay_mock'
    validate_condition_contract(config,resolve_prompt_set(config))
    configs.append(config)
report=validate_condition_matrix(configs)
print(json.dumps({'status':'passed','config_count':len(configs),'network_calls':0,'experiments_run':0,'condition_matrix':report},indent=2))
