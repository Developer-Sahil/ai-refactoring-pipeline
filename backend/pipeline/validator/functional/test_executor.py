# pipeline/validator/functional/test_executor.py
"""
Timeout-protected function executor.

Architecture note
-----------------
We use ``concurrent.futures.ThreadPoolExecutor`` for the timeout mechanism
because it is cross-platform (unlike ``signal.alarm`` which is POSIX-only).

Known limitation: if a function spins in a tight Python loop the background
thread cannot be forcibly killed — it will keep running after we return
``TimeoutError``.  For production use, replace the thread pool with a
``multiprocessing.Pool`` and serialise arguments via pickle.  The interface
of ``execute_with_timeout`` is identical in both cases, so swapping the
implementation does not require changes anywhere else.
"""
from __future__ import annotations

import concurrent.futures
import traceback
from typing import Any, Callable, Optional


# Sentinel distinguishes "function returned None" from "no result"
_NO_RESULT = object()


def execute_with_timeout(
    func: Callable,
    args: tuple,
    kwargs: dict,
    timeout: float = 5.0,
) -> tuple[bool, Any, Optional[str]]:
    """
    Call ``func(*args, **kwargs)`` with a wall-clock timeout.

    Returns
    -------
    ``(True,  result,  None)``        — normal return
    ``(False, None,   error_string)`` — exception or timeout

    Implementation note
    -------------------
    We call ``executor.shutdown(wait=False)`` after a timeout so the caller
    is not blocked by the still-running background thread.  The thread
    continues running in the background (Python cannot forcibly kill threads)
    but it will not hold up the validation pipeline.
    """
    def _call() -> Any:
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(func):
            # Run the coroutine in a fresh event loop inside this thread.
            # ThreadPoolExecutor threads have no running event loop, so
            # asyncio.run() is always safe here.
            return asyncio.run(func(*args, **kwargs))
        return func(*args, **kwargs)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_call)
    try:
        result = future.result(timeout=timeout)
        executor.shutdown(wait=False)
        return True, result, None
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)
        return False, None, f"TimeoutError: call exceeded {timeout:.1f}s"
    except Exception as exc:  # noqa: BLE001
        executor.shutdown(wait=False)
        tb = traceback.format_exc(limit=5)
        return False, None, f"{type(exc).__name__}: {exc}\n{tb}"


def batch_execute(
    func: Callable,
    input_list: list[tuple[tuple, dict]],
    timeout: float = 5.0,
) -> list[tuple[bool, Any, Optional[str]]]:
    """
    Convenience wrapper: execute *func* for every ``(args, kwargs)`` in
    *input_list* and return a parallel list of ``(success, result, error)``
    triples.
    """
    return [
        execute_with_timeout(func, args, kwargs, timeout)
        for args, kwargs in input_list
    ]
