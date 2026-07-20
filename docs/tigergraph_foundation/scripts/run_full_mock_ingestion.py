#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
fd, db_path=tempfile.mkstemp(prefix='iperform_mock_', suffix='.db')
os.close(fd)
os.unlink(db_path)
os.environ['MOCK_TIGERGRAPH']='true'
os.environ['TRACKER_DB_PATH']=db_path
sys.path.insert(0,str(ROOT/'backend'))

from app.services.ingestion_service import IngestionService

service=IngestionService()

def wait_for(run_id: str, timeout: int=300):
    deadline=time.time()+timeout
    while time.time()<deadline:
        status=service.status(run_id)
        if status and status['status'] in {'COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED'}:
            return status
        time.sleep(0.05)
    raise TimeoutError(f'Run {run_id} did not finish in {timeout}s')

def summarize(status: dict):
    keys=['run_id','status','total_files','completed_files','total_rows','processed_rows','succeeded_rows','failed_rows','skipped_rows','progress_pct','message']
    return {k:status.get(k) for k in keys}

try:
    first=wait_for(service.start(None, skip_unchanged=False, batch_size=1000))
    if first['status']!='COMPLETED' or first['succeeded_rows']!=154946 or first['failed_rows']!=0 or first['completed_files']!=185:
        raise RuntimeError(f'Initial mock load acceptance failed: {summarize(first)}')
    second=wait_for(service.start(None, skip_unchanged=True, batch_size=1000))
    if second['status']!='COMPLETED' or second['skipped_rows']!=154946 or second['failed_rows']!=0 or second['completed_files']!=185:
        raise RuntimeError(f'Unchanged reload acceptance failed: {summarize(second)}')
    report={
        'status':'PASS',
        'scope':'Mock orchestration and SQLite tracking only; this is not live TigerGraph compilation or execution.',
        'initial_load':summarize(first),
        'unchanged_reload':summarize(second),
        'initial_file_statuses':{x['status']:sum(1 for y in first['files'] if y['status']==x['status']) for x in first['files']},
        'unchanged_file_statuses':{x['status']:sum(1 for y in second['files'] if y['status']==x['status']) for x in second['files']},
        'row_errors':len(first['errors'])+len(second['errors']),
    }
    (ROOT/'reports/full_mock_ingestion.json').write_text(json.dumps(report,indent=2)+'\n')
    md=['# Full Mock Ingestion Validation','',f"**Status:** {report['status']}",'',
        '> This validates manifest orchestration, batching, exact acceptance accounting, SQLite progress/checkpoints, and unchanged-file skipping. It does not validate live TigerGraph schema/query compilation.','',
        '## Initial load']+[f"- {k}: {v}" for k,v in report['initial_load'].items()]+['','## Unchanged reload']+[f"- {k}: {v}" for k,v in report['unchanged_reload'].items()]+['',f"- Row errors: {report['row_errors']}"]
    (ROOT/'reports/full_mock_ingestion.md').write_text('\n'.join(md)+'\n')
    print(json.dumps(report,indent=2))
finally:
    for suffix in ('','-wal','-shm'):
        try: Path(db_path+suffix).unlink()
        except FileNotFoundError: pass
