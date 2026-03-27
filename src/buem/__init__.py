# Version: single source of truth is the git tag.
# Fallback chain: setuptools-scm (live from git) → _version.py → hardcoded fallback.
# The live git read avoids stale _version.py when using 'conda develop'.
try:
    from setuptools_scm import get_version as _scm_version
    __version__ = _scm_version()
except Exception:
    try:
        from buem._version import version as __version__
    except ImportError:
        __version__ = "0.1.3"  # keep in sync with pyproject.toml fallback_version
