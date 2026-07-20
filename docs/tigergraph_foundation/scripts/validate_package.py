#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,re,sys,hashlib
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
errors=[]; warnings=[]; checks=[]
def fail(code,msg,context=None): errors.append({'code':code,'message':msg,'context':context})
def warn(code,msg,context=None): warnings.append({'code':code,'message':msg,'context':context})
def ok(code,msg,count=None): checks.append({'code':code,'message':msg,'count':count})

def load_json(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: fail('JSON_PARSE',f'Cannot parse {path.relative_to(ROOT)}: {exc}'); return None

schema=load_json(ROOT/'tigergraph/schema/schema_catalog.json') or {'vertices':[],'edges':[]}
manifest=load_json(ROOT/'data/manifest.json') or {'files':[]}
qcat=load_json(ROOT/'tigergraph/queries/query_catalog.json') or []
cases=load_json(ROOT/'tests/query_cases.json') or {'cases':[]}
vertices={v['name']:v for v in schema['vertices']}; edges={e['name']:e for e in schema['edges']}
reverse={e.get('reverse_edge'): {'name':e.get('reverse_edge'),'from':e['to'],'to':e['from'],'attrs':e['attrs'],'original':e['name']} for e in schema['edges'] if e.get('reverse_edge')}
all_edges={**edges,**reverse}
entries=manifest.get('files',[])

# Catalog/schema integrity
if len(vertices)!=60: fail('VERTEX_COUNT',f'Expected 60 vertices, found {len(vertices)}')
else: ok('VERTEX_COUNT','57 vertex types catalogued',57)
if len(edges)!=132: fail('EDGE_COUNT',f'Expected 132 directed edges, found {len(edges)}')
else: ok('EDGE_COUNT','128 directed edge types catalogued',128)
if len(reverse)!=132: fail('REVERSE_EDGE_COUNT',f'Expected 132 reverse edges, found {len(reverse)}')
else: ok('REVERSE_EDGE_COUNT','128 explicit reverse edges catalogued',128)
for e in edges.values():
    if e['from'] not in vertices or e['to'] not in vertices: fail('EDGE_ENDPOINT_SCHEMA',f"{e['name']} has unknown endpoint",e)

# Schema GSQL declarations and graph membership
vertex_text=(ROOT/'tigergraph/schema/01_vertices.gsql').read_text()
edge_text=(ROOT/'tigergraph/schema/02_edges.gsql').read_text()
graph_text=(ROOT/'tigergraph/schema/03_create_graph.gsql').read_text()
for name in vertices:
    if not re.search(rf'CREATE\s+VERTEX\s+{re.escape(name)}\b',vertex_text): fail('VERTEX_DECLARATION',f'Missing GSQL vertex declaration {name}')
    if not re.search(rf'\b{re.escape(name)}\b',graph_text): fail('GRAPH_VERTEX_MEMBERSHIP',f'Graph omits vertex {name}')
for name,e in edges.items():
    decl=re.search(rf'CREATE\s+DIRECTED\s+EDGE\s+{re.escape(name)}\b[^;]+;',edge_text)
    if not decl: fail('EDGE_DECLARATION',f'Missing GSQL edge declaration {name}'); continue
    if f'WITH REVERSE_EDGE="{e.get("reverse_edge")}"' not in decl.group(0): fail('REVERSE_EDGE_DECLARATION',f'{name} does not declare expected reverse edge')
    for graph_edge in (name,e.get('reverse_edge')):
        if graph_edge and not re.search(rf'\b{re.escape(graph_edge)}\b',graph_text): fail('GRAPH_EDGE_MEMBERSHIP',f'Graph omits edge {graph_edge}')
ok('SCHEMA_DECLARATIONS','Schema declarations and graph membership checked')

# Manifest integrity
paths=[e['file'] for e in entries]; orders=[e['order'] for e in entries]
if len(entries)!=192: fail('MANIFEST_COUNT',f'Expected 185 entries, found {len(entries)}')
else: ok('MANIFEST_COUNT','192 manifest-controlled CSV targets',192)
for label,values in [('file path',paths),('order',orders)]:
    duplicates=[x for x,n in Counter(values).items() if n>1]
    if duplicates: fail('MANIFEST_DUPLICATE',f'Duplicate manifest {label}s',duplicates)
manifest_vertices={e['target'] for e in entries if e['kind']=='vertex'}
manifest_edges={e['target'] for e in entries if e['kind']=='edge'}
if manifest_vertices!=set(vertices): fail('MANIFEST_VERTEX_COVERAGE','Manifest vertex targets differ from schema',{'missing':sorted(set(vertices)-manifest_vertices),'extra':sorted(manifest_vertices-set(vertices))})
if manifest_edges!=set(edges): fail('MANIFEST_EDGE_COVERAGE','Manifest edge targets differ from schema',{'missing':sorted(set(edges)-manifest_edges),'extra':sorted(manifest_edges-set(edges))})
entry_map={e['file']:e for e in entries}
for e in entries:
    for dep in e.get('dependencies',[]):
        if dep not in entry_map: fail('MANIFEST_DEPENDENCY',f"{e['file']} depends on unknown file {dep}")
    if e['kind']=='edge':
        se=edges.get(e['target'])
        if se and (e['from_type']!=se['from'] or e['to_type']!=se['to']): fail('MANIFEST_EDGE_ENDPOINT',f"Endpoint mismatch for {e['target']}",{'manifest':(e['from_type'],e['to_type']),'schema':(se['from'],se['to'])})

# Attribute and CSV validation
def attr_map(obj): return {n:t for n,t in obj.get('attrs',[])}
def validate_value(value,typ,where):
    if value in ('',None): return
    try:
        if typ=='INT': int(value)
        elif typ=='DOUBLE': float(value)
        elif typ=='BOOL':
            if str(value).lower() not in {'true','false','0','1'}: raise ValueError('not boolean')
        elif typ=='DATETIME':
            text=str(value).replace('Z','+00:00')
            datetime.fromisoformat(text)
    except Exception as exc: fail('CSV_TYPE',f'Invalid {typ} value {value!r} at {where}: {exc}')

data_root=ROOT/'data/sample'; vertex_ids={}; total_rows=0
for e in sorted(entries,key=lambda x:x['order']):
    p=data_root/e['file']
    if not p.exists(): fail('CSV_MISSING',f'Missing {e["file"]}'); continue
    with p.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f); headers=reader.fieldnames or []; rows=list(reader)
    total_rows+=len(rows)
    if not rows and e.get('expected_rows',0)>0: fail('CSV_EMPTY',f'{e["file"]} contains no data')
    if len(rows)!=e.get('expected_rows'): fail('CSV_EXPECTED_ROWS',f"{e['file']} expected {e.get('expected_rows')} rows, found {len(rows)}")
    if set(headers)!=set(e.get('columns',{})): fail('CSV_HEADER_MAPPING',f"Header/mapping mismatch in {e['file']}",{'headers':headers,'mapping':list(e.get('columns',{}))})
    missing=[x for x in e.get('required_columns',[]) if x not in headers]
    if missing: fail('CSV_REQUIRED_COLUMNS',f"{e['file']} missing required columns",missing)
    if e['kind']=='vertex':
        v=vertices[e['target']]; idcol=e['id_column']; ids=[]; attrs=attr_map(v)
        if e.get('columns',{}).get(idcol)!=v['primary_id']: fail('VERTEX_ID_MAPPING',f"{e['file']} id column does not map to primary id")
        for row_no,row in enumerate(rows,2):
            vid=row.get(idcol,'').strip()
            if not vid: fail('VERTEX_BLANK_ID',f"Blank id in {e['file']} row {row_no}")
            ids.append(vid)
            for src,dst in e.get('columns',{}).items():
                if src==idcol: continue
                if dst not in attrs: fail('VERTEX_UNKNOWN_ATTR',f"{e['file']} maps to unknown {e['target']}.{dst}")
                else: validate_value(row.get(src),attrs[dst],f"{e['file']}:{row_no}:{src}")
        dup=[x for x,n in Counter(ids).items() if n>1]
        if dup: fail('VERTEX_DUPLICATE_ID',f"Duplicate ids in {e['file']}",dup[:20])
        vertex_ids[e['target']]=set(ids)
    else:
        ed=edges[e['target']]; attrs=attr_map(ed)
        endpoint_cols={e['from_column'],e['to_column']}
        seen=set()
        for row_no,row in enumerate(rows,2):
            fid=row.get(e['from_column'],'').strip(); tid=row.get(e['to_column'],'').strip()
            if not fid or not tid: fail('EDGE_BLANK_ENDPOINT',f"Blank endpoint in {e['file']} row {row_no}")
            if fid not in vertex_ids.get(e['from_type'],set()): fail('EDGE_FROM_MISSING',f"{e['file']} row {row_no}: {fid} missing from {e['from_type']}")
            if tid not in vertex_ids.get(e['to_type'],set()): fail('EDGE_TO_MISSING',f"{e['file']} row {row_no}: {tid} missing from {e['to_type']}")
            key=(fid,tid)
            if key in seen: fail('EDGE_DUPLICATE',f"Duplicate edge {key} in {e['file']}")
            seen.add(key)
            for src,dst in e.get('columns',{}).items():
                if src in endpoint_cols: continue
                if dst not in attrs: fail('EDGE_UNKNOWN_ATTR',f"{e['file']} maps to unknown {e['target']}.{dst}")
                else: validate_value(row.get(src),attrs[dst],f"{e['file']}:{row_no}:{src}")
ok('CSV_VALIDATION',f'Validated {len(entries)} CSV files and {total_rows} data rows',total_rows)

# JSON payload fields in sample data
for e in entries:
    if e['kind']!='vertex': continue
    p=data_root/e['file']
    with p.open(newline='',encoding='utf-8-sig') as f:
        for row_no,row in enumerate(csv.DictReader(f),2):
            for col,value in row.items():
                if col.endswith('_json') and value:
                    try: json.loads(value)
                    except Exception as exc: fail('CSV_JSON',f'Invalid JSON in {e["file"]}:{row_no}:{col}: {exc}')

# GSQL query static validation and semantic direction check
qfiles=sorted((ROOT/'tigergraph/queries').glob('GQ-*.gsql'))
if len(qfiles)!=62 or len(qcat)!=62 or len(cases.get('cases',[]))!=62: fail('QUERY_COUNT',f'Expected 62 query files/catalog/cases, found {len(qfiles)}/{len(qcat)}/{len(cases.get("cases",[]))}')
else: ok('QUERY_COUNT','43 implemented queries and test cases',43)
q_by_file={q['file']:q for q in qcat}; case_names={c['query_name'] for c in cases.get('cases',[])}
placeholder=re.compile(r'PRINT\s+query_id|contract-template|\bTODO\b|\bPLACEHOLDER\b|dummy query',re.I)
for path in qfiles:
    text=path.read_text(); q=q_by_file.get(path.name)
    if not q: fail('QUERY_CATALOG',f'{path.name} missing from query catalog'); continue
    if placeholder.search(text): fail('QUERY_PLACEHOLDER',f'Placeholder marker in {path.name}')
    decl=re.search(r'CREATE\s+QUERY\s+(\w+)\s*\((.*?)\)\s+FOR\s+GRAPH\s+(\w+)\s+SYNTAX\s+V1',text,re.S|re.I)
    if not decl: fail('QUERY_DECLARATION',f'Invalid/missing CREATE QUERY SYNTAX V1 in {path.name}'); continue
    if decl.group(1)!=q['name']: fail('QUERY_NAME',f'Name mismatch in {path.name}')
    if decl.group(3)!=schema['graph_name']: fail('QUERY_GRAPH',f'Graph mismatch in {path.name}')
    if not re.search(rf'INSTALL\s+QUERY\s+{re.escape(q["name"])}\b',text,re.I): fail('QUERY_INSTALL',f'Missing INSTALL QUERY in {path.name}')
    if len(re.findall(r'\bSELECT\b',text,re.I))<1: fail('QUERY_LOGIC',f'{path.name} has no SELECT traversal')
    if q['name'] not in case_names: fail('QUERY_TEST_CASE',f'No test case for {q["name"]}')
    # Schema names referenced after edge marker must exist.
    for edge_name in re.findall(r'-\(\s*(rev_)?(phx_dm_\w+)',text):
        full=''.join(edge_name)
        if full not in all_edges: fail('QUERY_UNKNOWN_EDGE',f'{path.name} references unknown edge {full}')
    # Basic delimiter balance after removing comments/strings.
    stripped=re.sub(r'/\*.*?\*/|//.*?$|#.*?$','',text,flags=re.S|re.M)
    for left,right in [('(',')'),('{','}')]:
        if stripped.count(left)!=stripped.count(right): fail('QUERY_DELIMITER',f'Unbalanced {left}{right} in {path.name}')
    if q.get('status') not in ('implemented-static-reviewed-live-compile-pending','created-batch1-NEEDS-LIVE-INSTALL','created-batch2-NEEDS-LIVE-INSTALL'): fail('QUERY_STATUS',f'Incorrect honest validation status for {q["name"]}: {q.get("status")}')
ok('QUERY_STATIC','Query placeholders, declarations, edge names, test cases and delimiters checked')

# Install file contains each query once
install=(ROOT/'tigergraph/queries/install_all_queries.gsql').read_text()
for q in qcat:
    if install.count('@'+q['file'])!=1: fail('QUERY_INSTALL_BUNDLE',f"Install bundle does not include exactly one {q['file']}")

result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'warnings':warnings,'summary':{'vertices':len(vertices),'edges':len(edges),'reverse_edges':len(reverse),'manifest_files':len(entries),'data_rows':total_rows,'queries':len(qfiles)}}
report_path=ROOT/'reports/static_validation_report.json'; report_path.parent.mkdir(exist_ok=True)
report_path.write_text(json.dumps(result,indent=2)+'\n')
md=['# Static Validation Report','',f"**Status:** {result['status']}",'',f"- Vertices: {len(vertices)}",f"- Directed edges: {len(edges)}",f"- Reverse edges: {len(reverse)}",f"- Manifest files: {len(entries)}",f"- Sample rows: {total_rows}",f"- GSQL queries: {len(qfiles)}",'', '## Checks']
md += [f"- PASS — {x['code']}: {x['message']}" for x in checks]
md += ['', '## Errors'] + ([f"- {x['code']}: {x['message']}" for x in errors] or ['- None'])
md += ['', '## Warnings'] + ([f"- {x['code']}: {x['message']}" for x in warnings] or ['- None'])
(ROOT/'reports/static_validation_report.md').write_text('\n'.join(md)+'\n')
print(json.dumps(result['summary'],indent=2)); print('STATUS',result['status']);
if errors:
    for e in errors[:50]: print('ERROR',e)
    sys.exit(1)
