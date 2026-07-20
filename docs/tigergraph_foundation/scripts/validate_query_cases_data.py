#!/usr/bin/env python3
from __future__ import annotations
import csv, json, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=json.load(open(ROOT/'data/manifest.json'))['files']
cases=json.load(open(ROOT/'tests/query_cases.json'))['cases']
data_root=ROOT/'data/sample'
errors=[]; checks=[]

def read_rows(target):
    entry=next(x for x in manifest if x['target']==target)
    with open(data_root/entry['file'],newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f)), entry

# IDs by vertex type and by primary-id field name.
ids_by_type={}; ids_by_field=defaultdict(set)
for e in manifest:
    if e['kind']!='vertex': continue
    with open(data_root/e['file'],newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    ids={r[e['id_column']] for r in rows}
    ids_by_type[e['target']]=ids
    ids_by_field[e['id_column']].update(ids)

param_type={
    'user_id':'phx_dm_persona_user','persona_user_id':'phx_dm_persona_user',
    'advisor_id':'phx_dm_advisor','household_id':'phx_dm_household','account_id':'phx_dm_account',
    'enrollment_id':'phx_dm_agp_enrollment','milestone_id':'phx_dm_agp_milestone',
    'feature_snapshot_id':'phx_dm_feature_snapshot','recommendation_id':'phx_dm_recommendation',
    'execution_id':'phx_dm_agent_execution','program_id':'phx_dm_agp_program',
}
dynamic_type={
    'FIRM':'phx_dm_firm','DIVISION':'phx_dm_division','REGION':'phx_dm_region','MARKET':'phx_dm_market',
    'BRANCH':'phx_dm_branch','ADVISOR':'phx_dm_advisor','HOUSEHOLD':'phx_dm_household',
    'ACCOUNT':'phx_dm_account','PRODUCT':'phx_dm_product','RECOMMENDATION':'phx_dm_recommendation',
    'PREDICTION':'phx_dm_prediction_result','OPPORTUNITY':'phx_dm_opportunity'
}
valid_enums={
    'scope_type':set(dynamic_type)|{'ALL'},'entity_type':{'ADVISOR','HOUSEHOLD','ACCOUNT','PRODUCT'},
    'target_type':{'ADVISOR','HOUSEHOLD','ACCOUNT'},'root_type':{'ADVISOR','HOUSEHOLD','ACCOUNT','PRODUCT'},
    'subject_type':{'ADVISOR','HOUSEHOLD'},'artifact_type':{'PREDICTION','OPPORTUNITY','RECOMMENDATION'},
    'period_type':{'LTM','YTD','MONTH','QUARTER','ANNUAL','CUSTOM'},'period_grain':{'MONTH','QUARTER','ANNUAL'},
    'direction':{'TOP','BOTTOM'},'peer_method':{'MARKET','SIMILARITY','HYBRID'},
    'query_intent':{'ALL','FEATURE','PREDICTION','OPPORTUNITY','RECOMMENDATION','COACHING','CRM','MEMORY','KNOWLEDGE'},
    'status':{'ALL','ACTIVE','OPEN','PENDING','COMPLETED','OVERDUE','CONVERTED','WON','LOST'},
    'severity':{'ALL','INFO','ATTENTION','URGENT','CRITICAL'}
}

# Relations used for authorization checks.
def edge_pairs(target):
    rows,e=read_rows(target)
    return {(r[e['from_column']],r[e['to_column']]) for r in rows}
user_firm=edge_pairs('phx_dm_user_scoped_to_firm'); user_div=edge_pairs('phx_dm_user_scoped_to_division')
user_region=edge_pairs('phx_dm_user_scoped_to_region'); user_market=edge_pairs('phx_dm_user_scoped_to_market')
user_branch=edge_pairs('phx_dm_user_scoped_to_branch'); user_advisor=edge_pairs('phx_dm_user_represents_advisor')
div_firm=edge_pairs('phx_dm_division_in_firm'); region_div=edge_pairs('phx_dm_region_in_division')
market_region=edge_pairs('phx_dm_market_in_region'); branch_market=edge_pairs('phx_dm_branch_in_market')
advisor_branch=edge_pairs('phx_dm_advisor_in_branch'); advisor_market=edge_pairs('phx_dm_advisor_in_market')
users,_=read_rows('phx_dm_persona_user'); roles={r['user_id']:r['role_code'] for r in users}

def authorized(user,advisor):
    if roles.get(user) in {'ADMIN','AI_OPS','COMPLIANCE'}: return True
    if (user,advisor) in user_advisor: return True
    a_branches={b for a,b in advisor_branch if a==advisor}; a_markets={m for a,m in advisor_market if a==advisor}
    if any((user,b) in user_branch for b in a_branches): return True
    if any((user,m) in user_market for m in a_markets): return True
    a_regions={r for m,r in market_region if m in a_markets}
    if any((user,r) in user_region for r in a_regions): return True
    a_divs={d for r,d in region_div if r in a_regions}
    if any((user,d) in user_div for d in a_divs): return True
    a_firms={f for d,f in div_firm if d in a_divs}
    return any((user,f) in user_firm for f in a_firms)

for case in cases:
    cid=case['id']; params=case.get('params',{})
    if not case.get('required_result_keys'):
        errors.append(f'{cid}: required_result_keys is empty')
    for key,allowed in valid_enums.items():
        if key in params and params[key] not in allowed:
            errors.append(f'{cid}: invalid {key}={params[key]!r}')
    for key,vtype in param_type.items():
        if key in params and params[key] not in ids_by_type[vtype]:
            errors.append(f'{cid}: {key}={params[key]!r} not found in {vtype}')
    # Dynamic IDs coupled to a type parameter.
    for type_key,id_key in [('scope_type','scope_id'),('entity_type','entity_id'),('target_type','target_id'),
                            ('root_type','root_id'),('subject_type','subject_id'),('artifact_type','artifact_id')]:
        if type_key in params and id_key in params and params[type_key] != 'ALL':
            vtype=dynamic_type.get(params[type_key])
            if vtype and params[id_key] not in ids_by_type[vtype]:
                errors.append(f'{cid}: {id_key}={params[id_key]!r} not found for {type_key}={params[type_key]}')
    if 'start_date' in params and 'end_date' in params:
        try:
            start=datetime.fromisoformat(params['start_date']); end=datetime.fromisoformat(params['end_date'])
            if start>end: errors.append(f'{cid}: start_date is after end_date')
        except ValueError as exc: errors.append(f'{cid}: invalid date: {exc}')
    for key in ('result_limit','node_limit'):
        if key in params and int(params[key])<=0: errors.append(f'{cid}: {key} must be positive')
    if 'max_depth' in params and int(params['max_depth'])<0: errors.append(f'{cid}: max_depth must be nonnegative')
    if 'min_score' in params and not 0<=float(params['min_score'])<=1: errors.append(f'{cid}: min_score must be 0..1')
    if 'persona_user_id' in params and 'subject_id' in params and not authorized(params['persona_user_id'],params['subject_id']):
        errors.append(f"{cid}: {params['persona_user_id']} is not authorized for advisor {params['subject_id']}")
    if cid=='GQ-040':
        user=params['persona_user_id']; scope_type=params['scope_type']; scope_id=params['scope_id']
        relation={'FIRM':user_firm,'DIVISION':user_div,'REGION':user_region,'MARKET':user_market,'BRANCH':user_branch}.get(scope_type)
        if roles.get(user) not in {'ADMIN','AI_OPS','COMPLIANCE'} and relation is not None and (user,scope_id) not in relation:
            errors.append(f'{cid}: user {user} is not assigned to requested {scope_type} {scope_id}')
    checks.append(cid)

result={'status':'PASS' if not errors else 'FAIL','query_cases':len(cases),'checks':len(checks),'errors':errors}
(ROOT/'reports/query_case_data_validation.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Query Case Data Validation','',f"**Status:** {result['status']}",'',f"- Query cases: {len(cases)}",f"- Errors: {len(errors)}"]
if errors: lines += ['','## Errors']+[f'- {e}' for e in errors]
(ROOT/'reports/query_case_data_validation.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'status':result['status'],'query_cases':len(cases),'errors':len(errors)},indent=2))
if errors:
    for e in errors: print('ERROR',e)
    sys.exit(1)
