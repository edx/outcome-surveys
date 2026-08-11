"""
Utilities for `outcome_surveys`.
"""

from importlib import import_module


def optional_lms_import(module_path, attribute):
    """
    Import `attribute` from `module_path`, returning None when that module is not installed.

    Only absent top-level LMS packages (e.g. `common.djangoapps`) are tolerated.
    Missing attributes or transitive import failures propagate as normal errors.
    """
    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        missing_module = exc.name
        is_the_optional_module = missing_module is not None and (
            module_path == missing_module or module_path.startswith(missing_module + '.')
        )
        if not is_the_optional_module:
            raise
        return None

    return getattr(module, attribute)
