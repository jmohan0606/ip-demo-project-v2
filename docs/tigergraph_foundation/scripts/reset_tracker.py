from pathlib import Path
p=Path(__file__).resolve().parents[1]/'runtime'/'ingestion_tracker.db'
if p.exists(): p.unlink(); print(f'Removed {p}')
else: print('Tracker database does not exist.')
