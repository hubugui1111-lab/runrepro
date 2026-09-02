"""Typed errors used at the CLI boundary."""


class RunReproError(Exception):
    """Base class for expected, user-facing RunRepro failures."""


class InvalidRunURLError(RunReproError, ValueError):
    """Raised when an input is not a canonical GitHub Actions run URL."""


class WorkflowAnalysisError(RunReproError):
    """Raised when a remote job cannot be mapped to one workflow job safely."""


class GitHubAPIError(RunReproError):
    """Raised when GitHub metadata cannot be collected."""


class BundleError(RunReproError):
    """Raised when a replay bundle cannot be prepared or loaded."""


class ReplayError(RunReproError):
    """Raised when the local replay runner cannot be started safely."""
