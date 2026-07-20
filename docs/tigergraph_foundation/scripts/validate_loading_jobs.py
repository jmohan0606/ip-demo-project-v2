#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'data/manifest.json').read_text())['files']
schema=json.loads((ROOT/'tigergraph/schema/schema_catalog.json').read_text())
catalog=json.loads((ROOT/'tigergraph/loading/loading_job_catalog.json').read_text())
vertices={v['name']:v for v in schema['vertices']}; edges={e['name']:e for e in schema['edges']}
errors=[]; rows=[]
if len(catalog)!=len(manifest): errors.append(f'Catalog count {len(catalog)} != manifest count {len(manifest)}')
cat_by_order={x['order']:x for x in catalog}
for entry in manifest:
    order=entry['order']; item=cat_by_order.get(order)
    if not item:
        errors.append(f'Missing loading job catalog order {order}'); continue
    if item['target']!=entry['target'] or item['kind']!=entry['kind'] or item['csv']!=entry['file']:
        errors.append(f'Catalog mismatch at order {order}: {item} vs {entry["target"]}/{entry["file"]}')
    path=ROOT/'tigergraph/loading/jobs'/item['file']
    if not path.exists(): errors.append(f'Missing job file {item["file"]}'); continue
    text=path.read_text()
    kind='VERTEX' if entry['kind']=='vertex' else 'EDGE'
    if not re.search(rf'CREATE\s+LOADING\s+JOB\s+{re.escape(item["job_name"])}\s+FOR\s+GRAPH\s+{re.escape(schema["graph_name"])}',text,re.I):
        errors.append(f'{item["file"]}: invalid CREATE LOADING JOB declaration')
    m=re.search(rf'LOAD\s+input_file\s+TO\s+{kind}\s+{re.escape(entry["target"])}\s+VALUES\s*\((.*?)\)',text,re.S|re.I)
    if not m:
        errors.append(f'{item["file"]}: missing LOAD target/VALUES'); continue
    actual=re.findall(r'\$"([^"]+)"',m.group(1))
    if entry['kind']=='vertex':
        v=vertices[entry['target']]
        expected_attrs=[v['primary_id']]+[a[0] for a in v['attrs']]
        inverse={dst:src for src,dst in entry['columns'].items()}
        expected=[inverse[x] for x in expected_attrs]
    else:
        e=edges[entry['target']]
        expected_attrs=[a[0] for a in e['attrs']]
        inverse={dst:src for src,dst in entry['columns'].items()}
        expected=[entry['from_column'],entry['to_column']]+[inverse[x] for x in expected_attrs]
    if actual!=expected:
        errors.append(f'{item["file"]}: VALUES order mismatch actual={actual} expected={expected}')
    if 'USING HEADER="true"' not in text or 'SEPARATOR=","' not in text:
        errors.append(f'{item["file"]}: missing CSV HEADER/SEPARATOR options')
    rows.append({'order':order,'job':item['job_name'],'target':entry['target'],'kind':entry['kind'],'columns':len(actual),'status':'PASS'})
install=(ROOT/'tigergraph/loading/install_all_loading_jobs.gsql').read_text()
for item in catalog:
    if install.count('@jobs/'+item['file'])!=1:
        errors.append(f'Install bundle missing or duplicates {item["file"]}')
report={'status':'PASS' if not errors else 'FAIL','job_count':len(rows),'errors':errors,'jobs':rows}
(ROOT/'reports/loading_job_audit.json').write_text(json.dumps(report,indent=2)+'\n')
md=['# Loading Job Audit','',f"**Status:** {report['status']}",f"**Jobs checked:** {len(rows)}",'',
    '> These jobs are a server-side fallback. The primary loader is the React → FastAPI → RESTPP ingestion flow.','',
    '## Errors']+([f'- {x}' for x in errors] or ['- None'])
(ROOT/'reports/loading_job_audit.md').write_text('\n'.join(md)+'\n')
print(f'Loading job audit {report["status"]}: {len(rows)} jobs; {len(errors)} error(s).')
for e in errors[:30]: print('ERROR',e)
if errors: sys.exit(1)
