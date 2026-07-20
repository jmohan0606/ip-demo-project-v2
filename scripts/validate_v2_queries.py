"""Static verification of the V2 GSQL query pack (QUERY_SPEC §6).

Checks: syntax rules (type-first params, USE GRAPH, SYNTAX V1, INSTALL QUERY,
one hop per SELECT), every referenced vertex/edge type exists in
schema_catalog.json, catalog<->file<->installer consistency, every catalog
query has a registered local-tier impl and a query_cases.json entry.
"""
import json, re, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QDIR = 'docs/tigergraph_foundation/tigergraph/queries/'
SDIR = 'docs/tigergraph_foundation/tigergraph/schema/'

def main() -> int:
    cat = json.load(open(QDIR + 'query_catalog.json'))
    schema = json.load(open(SDIR + 'schema_catalog.json'))
    vtypes = set(schema['vertices'])
    etypes = set(schema['edges']) | {e['reverse_edge'] for e in schema['edges'].values()}
    errors = []
    for q in cat['queries']:
        path = QDIR + q['file']
        if not os.path.exists(path):
            errors.append(f"{q['id']}: file missing"); continue
        body = re.sub(r'/\*.*?\*/', '', open(path).read(), flags=re.S)
        if 'USE GRAPH iperform_v2_revenue' not in body: errors.append(f"{q['id']}: missing USE GRAPH")
        if 'SYNTAX V1' not in body: errors.append(f"{q['id']}: missing SYNTAX V1")
        if f"INSTALL QUERY {q['name']}" not in body: errors.append(f"{q['id']}: missing INSTALL QUERY")
        m = re.search(r'CREATE QUERY (\w+)\((.*?)\)', body)
        if m.group(1) != q['name']: errors.append(f"{q['id']}: name mismatch {m.group(1)}")
        declared = [p.strip() for p in m.group(2).split(',') if p.strip()]
        parsed = []
        for d in declared:
            t, n = d.split()
            if t not in {'STRING', 'INT', 'DOUBLE', 'BOOL', 'DATETIME'}:
                errors.append(f"{q['id']}: param not type-first: '{d}'")
            parsed.append((n, t))
        if parsed != [(p['name'], p['type']) for p in q['parameters']]:
            errors.append(f"{q['id']}: catalog/file param mismatch")
        for name in re.findall(r'\{(phx_dm_v2_\w+)\.\*\}', body):
            if name not in vtypes: errors.append(f"{q['id']}: unknown vertex {name}")
        for edge, vt in re.findall(r'-\((\w+):\w+\)-\s*(\w+):', body):
            if edge not in etypes: errors.append(f"{q['id']}: unknown edge {edge}")
            if vt not in vtypes: errors.append(f"{q['id']}: traversal target not a vertex TYPE: {vt}")
        for sel in re.findall(r'SELECT .*?;', body, re.S):
            if sel.count('-(') > 1: errors.append(f"{q['id']}: multi-hop SELECT")
    install = open(QDIR + 'install_all_queries.gsql').read()
    for q in cat['queries']:
        if q['file'] not in install: errors.append(f"{q['id']}: not in install_all_queries.gsql")
    from app.graph.client import MOCK_QUERY_IMPLS
    import app.graph.queries  # noqa: F401 — registers implementations
    cases = json.load(open(QDIR + 'tests/query_cases.json'))
    for q in cat['queries']:
        if q['name'] not in MOCK_QUERY_IMPLS: errors.append(f"{q['id']}: no local-tier impl")
        if q['name'] not in cases: errors.append(f"{q['id']}: no query_cases entry")
    print("ERRORS:" if errors else "ALL CHECKS PASS", *errors, sep='\n')
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main())
