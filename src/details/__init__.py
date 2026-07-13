"""detailgen.details — the ``Detail`` base class authors subclass to build a
whole construction detail as one parameterizable object.

Runnable detail *scripts* live in the repo-root ``details/`` folder and each
define a ``Detail`` subclass here; this package is the framework they build on.
"""

from .base import Detail, Callout, fmt_frac_in

__all__ = ["Detail", "Callout", "fmt_frac_in"]
