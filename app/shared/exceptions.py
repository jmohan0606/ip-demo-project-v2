class IPerformError(Exception): pass
class ConfigurationError(IPerformError): pass
class ExternalServiceError(IPerformError): pass
class ValidationError(IPerformError): pass
class NotFoundError(IPerformError): pass
class IngestionCheckpointError(IPerformError): pass
