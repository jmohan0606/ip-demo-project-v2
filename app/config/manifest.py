from app.config.constants import APP_DISPLAY_NAME, CORE_CAPABILITIES, GRAPH_NAME, SCHEMA_PREFIX

def project_manifest() -> dict:
    return {'application':APP_DISPLAY_NAME,'graph_name':GRAPH_NAME,'schema_prefix':SCHEMA_PREFIX,'package_stage':'11.0.3','foundation_status':'stabilized','capabilities_locked':CORE_CAPABILITIES,'next_part':'11.1 TigerGraph Foundation Package'}
