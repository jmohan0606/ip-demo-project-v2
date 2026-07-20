from datetime import datetime
from uuid import uuid4

def new_id(prefix: str) -> str:
    return f"{prefix.strip('_').lower()}_{uuid4().hex[:16]}"

def timestamp_id(prefix: str) -> str:
    return f"{prefix.strip('_').lower()}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
