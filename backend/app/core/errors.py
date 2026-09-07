"""Application errors whose public messages never include provider response bodies."""


class CitationValidationError(ValueError):
    pass


class ModelConfigurationError(ValueError):
    pass


class ModelServiceError(RuntimeError):
    pass
