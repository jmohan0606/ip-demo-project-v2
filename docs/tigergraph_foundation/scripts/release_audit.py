#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]; checks=[]

def passed(name,detail): checks.append({'check':name,'detail':detail})
def failed(name,detail): errors.append({'check':name,'detail':detail})

forbidden_names={'node_modules','dist','__pycache__','.pytest_cache'}
for p in ROOT.rglob('*'):
    rel=p.relative_to(ROOT)
    if any(part in forbidden_names for part in rel.parts): failed('BUILD_DEBRIS',str(rel))
    if p.is_file() and (p.suffix in {'.db','.pyc'} or p.name.endswith(('.db-wal','.db-shm','.tsbuildinfo'))): failed('BUILD_DEBRIS',str(rel))
passed('BUILD_DEBRIS_SCAN','No dependency folders, build outputs, bytecode or runtime databases')

actual_env=[p.relative_to(ROOT) for p in ROOT.rglob('.env')]
if actual_env: failed('ENV_FILE',f'Unexpected live .env files: {actual_env}')
else: passed('ENV_FILE','Only documented .env templates are present')

secret_patterns=[
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'Bearer\s+[A-Za-z0-9._-]{20,}'),
    re.compile(r'(?i)(?:api[_-]?key|secret|password|token)\s*[=:]\s*["\']?[A-Za-z0-9._-]{20,}')
]
for p in ROOT.rglob('*'):
    if not p.is_file() or any(part in {'.git'} for part in p.relative_to(ROOT).parts): continue
    if p.name in {'package-lock.json','release_audit.py','.env.example','.env.mock.example'}: continue
    try: text=p.read_text(encoding='utf-8')
    except UnicodeDecodeError: continue
    for pattern in secret_patterns:
        if pattern.search(text): failed('SECRET_SCAN',str(p.relative_to(ROOT))); break
if not any(e['check']=='SECRET_SCAN' for e in errors): passed('SECRET_SCAN','No likely credentials or private keys detected')

expected_version='0.2.0'
version_sources={
    'frontend/package.json':json.load(open(ROOT/'frontend/package.json'))['version'],
}
main=(ROOT/'backend/app/main.py').read_text()
m=re.search(r'version="([^"]+)"',main); version_sources['backend/app/main.py']=m.group(1) if m else 'MISSING'
readme=(ROOT/'README.md').read_text(); version_sources['README.md']=expected_version if f'v{expected_version}' in readme else 'MISSING'
for source,value in version_sources.items():
    if value!=expected_version: failed('VERSION',f'{source}={value}')
if not any(e['check']=='VERSION' for e in errors): passed('VERSION',f'Package version {expected_version} is consistent')

required=[
    'README.md','PACKAGE_STATUS.md','VALIDATION_REPORT.md','CHANGELOG.md','Makefile',
    'data/manifest.json','tigergraph/schema/00_install_schema.gsql',
    'tigergraph/loading/install_all_loading_jobs.gsql','tigergraph/queries/install_all_queries.gsql',
    'tests/query_cases.json','docs/live_tigergraph_runbook.md'
]
missing=[x for x in required if not (ROOT/x).exists()]
if missing: failed('REQUIRED_FILES',missing)
else: passed('REQUIRED_FILES',f'{len(required)} required release entry points present')

result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}
(ROOT/'reports/release_audit.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Release Audit','',f"**Status:** {result['status']}",'']+[f"- PASS — {x['check']}: {x['detail']}" for x in checks]
if errors: lines += ['','## Errors']+[f"- {x['check']}: {x['detail']}" for x in errors]
(ROOT/'reports/release_audit.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'status':result['status'],'checks':len(checks),'errors':len(errors)},indent=2))
if errors:
    for e in errors: print('ERROR',e)
    sys.exit(1)
