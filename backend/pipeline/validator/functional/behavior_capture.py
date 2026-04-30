# pipeline/validator/functional/behavior_capture.py
"""
Safe dynamic module importer and callable extractor.

Design goals
------------
* Never crash the parent process, even if the target module has top-level
  side effects, network calls, or import errors.
* Only surface functions that are *defined* in the target file (not
  re-exports from third-party libraries).
* Clean up sys.modules / sys.path after each import to avoid pollution
  between successive calls.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional


# ---------------------------------------------------------------------------
# Module importer
# ---------------------------------------------------------------------------

def safe_import_module(
    file_path: Path,
    timeout_secs: float = 10.0,
) -> tuple[Optional[ModuleType], str]:
    """
    Dynamically import *file_path* as an isolated module.

    Returns
    -------
    (module, "")           on success
    (None,  error_message) on any failure
    """
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        return None, f"File not found: {file_path}"
    if file_path.suffix != ".py":
        return None, f"Not a Python file: {file_path}"

    # Use a unique name to avoid collisions in sys.modules
    module_name = f"_vldr_{file_path.stem}_{abs(hash(str(file_path)))}"
    module_dir  = str(file_path.parent)

    path_was_modified = module_dir not in sys.path
    if path_was_modified:
        sys.path.insert(0, module_dir)

    # Clean up any previous import of the same logical name
    sys.modules.pop(module_name, None)

    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            return None, f"importlib could not build a spec for {file_path}"

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        # exec_module can raise anything; catch everything
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module, ""

    except SyntaxError as exc:
        return None, f"SyntaxError at line {exc.lineno}: {exc.msg}"
    except ImportError as exc:
        return None, f"ImportError: {exc}"
    except SystemExit as exc:
        return None, f"Module called sys.exit({exc.code}) at import time"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        # Remove path addition so subsequent imports are not affected
        if path_was_modified and module_dir in sys.path:
            sys.path.remove(module_dir)


# ---------------------------------------------------------------------------
# Callable extractor
# ---------------------------------------------------------------------------

def extract_callable_functions(module: ModuleType) -> dict[str, object]:
    """
    Return a ``{name: callable}`` dict of functions *defined* in *module*.

    Exclusion rules
    ---------------
    * Names starting with ``_`` (private / dunder)
    * Classes — we validate *functions*, not constructors
    * Built-in / C-extension callables
    * Functions whose ``__code__.co_filename`` points to a different file
      (i.e. imported re-exports from third-party libraries)
    """
    module_file = getattr(module, "__file__", None)
    if module_file:
        module_file = str(Path(module_file).resolve())

    callables: dict[str, object] = {}

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        if not callable(obj):
            continue
        if inspect.isclass(obj):
            continue
        if inspect.isbuiltin(obj):
            continue

        # Only keep functions defined in this file
        if inspect.isfunction(obj) and module_file:
            try:
                src_file = str(Path(inspect.getfile(obj)).resolve())
                if src_file != module_file:
                    continue
            except (TypeError, OSError):
                pass

        callables[name] = obj

    return callables
