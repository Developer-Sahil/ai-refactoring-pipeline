# pipeline/validator/functional/__init__.py
"""
Functional validation sub-package.

Public API
----------
capture_behavior          Run original functions, record (input, output) pairs.
replay_against_refactored Replay captured pairs on the refactored module.
run_all_property_checks   Check determinism, type-stability, exception contract.
generate_inputs_for_function  Generate typed inputs for any callable.
safe_import_module        Dynamically import a .py file without side effects.
extract_callable_functions    Extract public functions defined in a module.
execute_with_timeout      Call a function with a wall-clock timeout.
outputs_match             Deep equality check (float-tolerant, numpy-aware).
compute_aggregate         Turn ReplayResult lists into a summary dict.
"""

from .behavior_capture    import safe_import_module, extract_callable_functions
from .input_generator     import generate_inputs_for_function
from .test_executor       import execute_with_timeout, batch_execute
from .replay_test_builder import capture_behavior, replay_against_refactored, TestCase, ReplayResult
from .property_test_builder import run_all_property_checks, PropertyResult
from .result_analyzer     import outputs_match, compute_aggregate

__all__ = [
    # module loading
    "safe_import_module",
    "extract_callable_functions",
    # input generation
    "generate_inputs_for_function",
    # execution
    "execute_with_timeout",
    "batch_execute",
    # replay testing
    "capture_behavior",
    "replay_against_refactored",
    "TestCase",
    "ReplayResult",
    # property testing
    "run_all_property_checks",
    "PropertyResult",
    # analysis
    "outputs_match",
    "compute_aggregate",
]
