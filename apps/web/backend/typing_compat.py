import inspect
import sys
import typing
from typing import Any


def patch_typing_eval_type() -> None:
    """
    Work around Python 3.14 changes in the private `typing._eval_type()` API.

    Some versions of Pydantic call `typing._eval_type(..., prefer_fwd_module=...)`,
    but Python 3.14's `typing._eval_type()` no longer accepts that kwarg.
    """

    if sys.version_info < (3, 14):
        return

    eval_type = getattr(typing, "_eval_type", None)
    if eval_type is None:
        return

    if getattr(eval_type, "_convertapk_patched", False):
        return

    try:
        signature = inspect.signature(eval_type)
    except (TypeError, ValueError):
        signature = None

    if signature is not None and "prefer_fwd_module" in signature.parameters:
        return

    sentinel = getattr(typing, "_sentinel", object())
    original_eval_type = eval_type

    def _eval_type_compat(
        t: Any,
        globalns: Any,
        localns: Any,
        type_params: Any = sentinel,
        **kwargs: Any,
    ) -> Any:
        kwargs.pop("prefer_fwd_module", None)
        return original_eval_type(
            t, globalns, localns, type_params=type_params, **kwargs
        )

    _eval_type_compat._convertapk_patched = True  # type: ignore[attr-defined]
    typing._eval_type = _eval_type_compat  # type: ignore[attr-defined]
