from dataclasses import dataclass
from app.config.constants import GRAPH_NAME, SCHEMA_PREFIX
from app.config.settings import Settings

@dataclass(frozen=True)
class ConfigValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]

class ConfigValidator:
    def __init__(self, settings: Settings) -> None: self.settings = settings
    def validate(self) -> ConfigValidationResult:
        errors, warnings = [], []
        if self.settings.tigergraph_graph != GRAPH_NAME:
            errors.append(f"TIGERGRAPH_GRAPH must be {GRAPH_NAME}; got {self.settings.tigergraph_graph}")
        if self.settings.tigergraph_schema_prefix != SCHEMA_PREFIX:
            errors.append(f"TIGERGRAPH_SCHEMA_PREFIX must be {SCHEMA_PREFIX}; got {self.settings.tigergraph_schema_prefix}")
        if self.settings.enable_openai and not self.settings.openai_api_key: warnings.append('OPENAI_API_KEY is not configured; mock adapter will be used.')
        if self.settings.enable_tigergraph_mcp and not self.settings.tigergraph_mcp_url: warnings.append('TIGERGRAPH_MCP_URL is not configured.')
        if self.settings.enable_tigergraph_rest_fallback and not self.settings.tigergraph_host: warnings.append('TIGERGRAPH_HOST is not configured.')
        return ConfigValidationResult(valid=not errors, errors=errors, warnings=warnings)
