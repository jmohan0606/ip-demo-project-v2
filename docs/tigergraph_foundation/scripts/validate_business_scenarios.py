#!/usr/bin/env python3
from __future__ import annotations
import csv,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'data/sample/vertices'; E=ROOT/'data/sample/edges'
errors=[]; checks=[]

def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def check(name,condition,detail):
    if condition: checks.append({'check':name,'detail':detail})
    else: errors.append({'check':name,'detail':detail})
def one_parent(filename,child_col='from_id'):
    c=Counter(r[child_col] for r in rows(E/filename)); return min(c.values(),default=0)==1 and max(c.values(),default=0)==1

def edge_sources(filename): return Counter(r['from_id'] for r in rows(E/filename))
def edge_targets(filename): return Counter(r['to_id'] for r in rows(E/filename))

users=rows(V/'phx_dm_persona_user.csv')
roles=set(r['role_code'] for r in users)
required_roles={'EXEC','DDW','RDW','MDW','ADVISOR','AGP_ADVISOR','ADMIN','COMPLIANCE','AI_OPS'}
check('PERSONA_ROLES',required_roles<=roles,f'roles={sorted(roles)}')

for fn,expected in [('phx_dm_firm.csv',1),('phx_dm_division.csv',3),('phx_dm_region.csv',6),('phx_dm_market.csv',12),('phx_dm_branch.csv',24),('phx_dm_advisor.csv',60),('phx_dm_household.csv',360),('phx_dm_account.csv',720),('phx_dm_product.csv',64),('phx_dm_time_period.csv',36)]:
    actual=len(rows(V/fn)); check('COUNT_'+fn,actual==expected,f'expected={expected}, actual={actual}')

# Organization and management hierarchy completeness.
check('DIVISION_TO_FIRM',one_parent('phx_dm_division_in_firm.csv'), 'every division has one firm')
check('REGION_TO_DIVISION',one_parent('phx_dm_region_in_division.csv'), 'every region has one division')
check('MARKET_TO_REGION',one_parent('phx_dm_market_in_region.csv'), 'every market has one region')
check('BRANCH_TO_MARKET',one_parent('phx_dm_branch_in_market.csv'), 'every branch has one market')
check('ADVISOR_TO_BRANCH',one_parent('phx_dm_advisor_in_branch.csv'), 'every advisor has one branch')
check('ADVISOR_TO_MARKET',one_parent('phx_dm_advisor_in_market.csv'), 'every advisor has one market')
check('RDW_TO_DDW',one_parent('phx_dm_ddw_manages_rdw.csv','to_id'), 'every RDW is managed by one DDW')
check('MDW_TO_RDW',one_parent('phx_dm_rdw_manages_mdw.csv','to_id'), 'every MDW is managed by one RDW')
check('ADVISOR_TO_MDW',one_parent('phx_dm_mdw_manages_advisor.csv','to_id'), 'every advisor is managed by one MDW')

# Core book-of-business completeness.
check('HOUSEHOLD_TO_ADVISOR',one_parent('phx_dm_advisor_serves_household.csv','to_id'),'every household has one advisor')
check('ACCOUNT_TO_HOUSEHOLD',one_parent('phx_dm_household_owns_account.csv','to_id'),'every account has one household')
check('ACCOUNT_PRODUCT_COVERAGE',len(edge_sources('phx_dm_account_holds_product.csv'))==720,'every account has product holdings')

# AGP 24-month / 3-month milestone model.
milestones=rows(V/'phx_dm_agp_milestone.csv')
check('AGP_MILESTONE_MONTHS',sorted(int(r['milestone_month']) for r in milestones)==[3,6,9,12,15,18,21,24],'eight 3-month milestones through month 24')
enrollments=rows(V/'phx_dm_agp_enrollment.csv')
progress_counts=edge_sources('phx_dm_enrollment_has_milestone_progress.csv')
check('AGP_ENROLLMENTS',len(enrollments)==24,'24 AGP enrollments')
check('AGP_PROGRESS_PER_ENROLLMENT',set(progress_counts.values())=={8},'each enrollment has 8 milestone progress records')
measurement_counts=edge_sources('phx_dm_progress_has_kpi_measurement.csv')
check('AGP_KPI_PER_MILESTONE',set(measurement_counts.values())=={5},'each milestone progress has 5 KPI measurements')
progress_status=set(r['status'] for r in rows(V/'phx_dm_agp_milestone_progress.csv'))
check('AGP_STATUS_VARIETY',{'COMPLETED','ON_TRACK','AT_RISK','UPCOMING'}<=progress_status,f'statuses={sorted(progress_status)}')

# CRM operational scenarios.
lead_status=set(r['status'] for r in rows(V/'phx_dm_crm_lead.csv'))
ref_status=set(r['status'] for r in rows(V/'phx_dm_crm_referral.csv'))
opp_status=set(r['status'] for r in rows(V/'phx_dm_crm_opportunity.csv'))
opp_stage=set(r['stage'] for r in rows(V/'phx_dm_crm_opportunity.csv'))
check('CRM_LEAD_VARIETY',{'PENDING','COMPLETED','OVERDUE','CONVERTED'}<=lead_status,f'statuses={sorted(lead_status)}')
check('CRM_REFERRAL_VARIETY',{'PENDING','COMPLETED','OVERDUE','CONVERTED'}<=ref_status,f'statuses={sorted(ref_status)}')
check('CRM_OPPORTUNITY_OUTCOMES',{'OPEN','WON','LOST'}<=opp_status,f'statuses={sorted(opp_status)}')
check('CRM_PIPELINE_STAGES',{'QUALIFY','PROPOSE','NEGOTIATE','CLOSED_WON','CLOSED_LOST'}<=opp_stage,f'stages={sorted(opp_stage)}')

# AI simulation coverage.
for fn in ['phx_dm_prediction_result.csv','phx_dm_opportunity.csv','phx_dm_recommendation.csv']:
    severities=set(r['severity'] for r in rows(V/fn))
    check('SEVERITY_'+fn,{'INFO','ATTENTION','URGENT','CRITICAL'}<=severities,f'severities={sorted(severities)}')
mem_types=set(r['memory_type'] for r in rows(V/'phx_dm_context_memory.csv'))
check('MEMORY_TAXONOMY',{'SEMANTIC','EPISODIC','PREFERENCE','OUTCOME','REASONING'}<=mem_types,f'memory_types={sorted(mem_types)}')
feedback_actions=set(r['action'] for r in rows(V/'phx_dm_feedback_event.csv'))
check('FEEDBACK_ACTIONS',{'ACCEPT','REJECT','DEFER','NOT_RELEVANT','COMPLETE'}<=feedback_actions,f'actions={sorted(feedback_actions)}')

prediction_ids={r['prediction_id'] for r in rows(V/'phx_dm_prediction_result.csv')}
opportunity_ids={r['opportunity_id'] for r in rows(V/'phx_dm_opportunity.csv')}
recommendation_ids={r['recommendation_id'] for r in rows(V/'phx_dm_recommendation.csv')}

def all_sources(filename, expected): return set(r['from_id'] for r in rows(E/filename))==expected
check('PREDICTION_FEATURE_LINEAGE',all_sources('phx_dm_prediction_uses_feature_snapshot.csv',prediction_ids),'every prediction links to a feature snapshot')
check('PREDICTION_REASONING_LINEAGE',set(r['to_id'] for r in rows(E/'phx_dm_reasoning_for_prediction.csv'))==prediction_ids,'every prediction links to reasoning')
check('OPPORTUNITY_FEATURE_LINEAGE',all_sources('phx_dm_opportunity_uses_feature_snapshot.csv',opportunity_ids),'every opportunity links to a feature snapshot')
check('OPPORTUNITY_PREDICTION_LINEAGE',all_sources('phx_dm_opportunity_derived_from_prediction.csv',opportunity_ids),'every opportunity links to a prediction')
check('OPPORTUNITY_REASONING_LINEAGE',set(r['to_id'] for r in rows(E/'phx_dm_reasoning_for_opportunity.csv'))==opportunity_ids,'every opportunity links to reasoning')
check('RECOMMENDATION_FEATURE_LINEAGE',all_sources('phx_dm_recommendation_uses_feature_snapshot.csv',recommendation_ids),'every recommendation links to a feature snapshot')
check('RECOMMENDATION_OPPORTUNITY_LINEAGE',all_sources('phx_dm_recommendation_addresses_opportunity.csv',recommendation_ids),'every recommendation links to an opportunity')
check('RECOMMENDATION_PREDICTION_LINEAGE',all_sources('phx_dm_recommendation_based_on_prediction.csv',recommendation_ids),'every recommendation links to a prediction')
check('RECOMMENDATION_REASONING_LINEAGE',set(r['to_id'] for r in rows(E/'phx_dm_reasoning_for_recommendation.csv'))==recommendation_ids,'every recommendation links to reasoning')

# Time-series and transaction coverage.
periods=rows(V/'phx_dm_time_period.csv')
check('TIME_PERIOD_CONTINUITY',len(periods)==36 and len({r['period_id'] for r in periods})==36,'36 unique monthly periods')
tx_by_advisor=edge_targets('phx_dm_transaction_for_advisor.csv')
# Edge target is advisor because transaction->advisor.
check('TRANSACTION_ADVISOR_COVERAGE',len(tx_by_advisor)==60 and min(tx_by_advisor.values())>0,'all advisors have transactions')

result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'summary':{'checks':len(checks)+len(errors),'passed':len(checks),'failed':len(errors)}}
(ROOT/'reports/business_scenario_validation.json').write_text(json.dumps(result,indent=2)+'\n')
md=['# Business Scenario Validation','',f"**Status:** {result['status']}",f"- Passed: {len(checks)}",f"- Failed: {len(errors)}",'','## Passed Checks']+[f"- {x['check']}: {x['detail']}" for x in checks]+['','## Errors']+([f"- {x['check']}: {x['detail']}" for x in errors] or ['- None'])
(ROOT/'reports/business_scenario_validation.md').write_text('\n'.join(md)+'\n')
print(json.dumps(result['summary'],indent=2)); print('STATUS',result['status'])
for x in errors: print('ERROR',x)
if errors: sys.exit(1)
