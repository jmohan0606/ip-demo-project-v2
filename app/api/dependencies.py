from app.config.settings import Settings, get_settings
from app.services.runtime_status_service import RuntimeStatusService

def get_runtime_settings() -> Settings: return get_settings()
def get_runtime_status_service() -> RuntimeStatusService: return RuntimeStatusService()
