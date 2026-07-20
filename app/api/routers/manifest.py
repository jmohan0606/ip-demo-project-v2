from fastapi import APIRouter
from app.config.manifest import project_manifest
from app.shared.responses import ok
router=APIRouter(prefix='/manifest', tags=['Manifest'])
@router.get('')
def manifest(): return ok(data=project_manifest())
