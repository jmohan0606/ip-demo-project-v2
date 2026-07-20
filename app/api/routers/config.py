from fastapi import APIRouter
from app.config.settings import get_settings
from app.config.validation import ConfigValidator
from app.shared.responses import ok
router = APIRouter(prefix='/config', tags=['Config'])
@router.get('/summary')
def config_summary():
    s=get_settings(); v=ConfigValidator(s).validate()
    return ok(data={'app_name':s.app_name,'app_version':s.app_version,'environment':s.app_env,'graph_name':s.tigergraph_graph,'schema_prefix':s.tigergraph_schema_prefix,'sqlite_db_path':s.sqlite_db_path,'chroma_path':s.chroma_path,'openai_configured':bool(s.openai_api_key),'tigergraph_mcp_configured':bool(s.tigergraph_mcp_url),'tigergraph_rest_configured':bool(s.tigergraph_host),'valid':v.valid,'errors':v.errors,'warnings':v.warnings})
