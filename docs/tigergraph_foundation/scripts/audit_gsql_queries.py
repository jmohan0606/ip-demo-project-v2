#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QROOT=ROOT/'tigergraph/queries'
CAT=json.loads((QROOT/'query_catalog.json').read_text())
CASES=json.loads((ROOT/'tests/query_cases.json').read_text())['cases']
case_by_name={c['query_name']:c for c in CASES}
rows=[]; errors=[]

for meta in CAT:
    p=QROOT/meta['file']; text=p.read_text()
    decl=re.search(r'CREATE\s+QUERY\s+(\w+)\s*\((.*?)\)\s+FOR\s+GRAPH\s+(\w+)\s+SYNTAX\s+V1',text,re.S|re.I)
    if not decl:
        errors.append(f"{p.name}: missing valid CREATE QUERY declaration")
        continue
    params=[]
    for item in decl.group(2).split(','):
        item=item.strip()
        if item:
            m=re.match(r'([A-Za-z_]\w*)\s+',item)
            if m: params.append(m.group(1))
    body=text[decl.end():]
    # Remove PRINT statements for semantic parameter usage check.
    body_without_print=re.sub(r'\bPRINT\b.*?;', '', body, flags=re.S|re.I)
    unused=[x for x in params if not re.search(rf'\b{re.escape(x)}\b',body_without_print)]
    # period_type is intentionally validation metadata and is used by valid_period_type.
    if unused:
        errors.append(f"{p.name}: parameter(s) only echoed or unused: {', '.join(unused)}")
    select_count=len(re.findall(r'\bSELECT\b',text,re.I))
    traversal_count=len(re.findall(r'-\(\s*(?:rev_)?phx_dm_',text))
    accum_count=len(re.findall(r'\b(?:SumAccum|GroupByAccum|OrAccum|AndAccum|MaxAccum|MinAccum|ListAccum|SetAccum)\b',text))
    has_where=bool(re.search(r'\bWHERE\b',text,re.I))
    has_print=bool(re.search(r'\bPRINT\b',text,re.I))
    has_case=meta['name'] in case_by_name
    rows.append({
        'id':meta['id'],'name':meta['name'],'file':p.name,
        'parameters':params,'unused_parameters':unused,
        'select_count':select_count,'traversal_count':traversal_count,
        'accumulator_count':accum_count,'has_where':has_where,
        'has_print':has_print,'has_test_case':has_case,
        'static_status':'PASS' if not unused and select_count and has_print and has_case else 'FAIL',
        'live_compile_status':'PENDING_EXTERNAL_TIGERGRAPH_4_2_2'
    })

report={'status':'PASS' if not errors else 'FAIL','queries':rows,'errors':errors}
(ROOT/'reports/query_audit.json').write_text(json.dumps(report,indent=2)+'\n')
md=['# GSQL Query Audit','',f"**Static status:** {report['status']}",'',
    '> Live compilation and execution require the external TigerGraph 4.2.2 environment and are not claimed in this package.','',
    '| ID | Query | Parameters | SELECTs | Traversals | Accumulators | Test case | Static | Live |',
    '|---|---|---:|---:|---:|---:|---|---|---|']
for r in rows:
    md.append(f"| {r['id']} | `{r['name']}` | {len(r['parameters'])} | {r['select_count']} | {r['traversal_count']} | {r['accumulator_count']} | {'Yes' if r['has_test_case'] else 'No'} | {r['static_status']} | Pending |")
md += ['', '## Errors'] + ([f'- {e}' for e in errors] or ['- None'])
(ROOT/'reports/query_audit.md').write_text('\n'.join(md)+'\n')
print(f"Query audit {report['status']}: {len(rows)} queries; {len(errors)} error(s).")
for e in errors: print('ERROR',e)
if errors: sys.exit(1)
