class FastChimeraError(Exception):
    """Base class for every error raised by FastChimera."""


class ConfigurationError(FastChimeraError):
    """Missing or invalid configuration (e.g. no Gemini API key)."""


class LlmAPIError(FastChimeraError):
    """The LLM provider refused the request or could not be reached."""


class LlmResponseError(FastChimeraError):
    """The LLM answered, but the answer could not be parsed or validated."""


class PlanningError(FastChimeraError):
    """A plan (features, roadmap or phase) could not be produced."""


class AstParsingError(FastChimeraError):
    """Raised when scanning or editing source code via AST/LibCST fails."""


class CodeValidationError(FastChimeraError):
    """Generated code failed validation and could not be repaired."""


class UnsafePathError(FastChimeraError, ValueError):
    """A file path is absolute, escapes the project, or is otherwise not allowed."""


class FileConflictError(FastChimeraError):
    """A file exists, was not created by FastChimera, and overwriting was not allowed."""


class FileGenerationError(FastChimeraError):
    """Generating or writing a file failed."""


class VerificationError(FastChimeraError):
    """The verification tooling itself failed (not the generated code)."""


class StateError(FastChimeraError):
    """The saved build state is missing or corrupt."""


class ShiftError(FastChimeraError):
    """Building or sending the project fingerprint failed."""


class ShiftConfigError(ShiftError):
    """The SHIFT_* settings are missing or unsafe."""
