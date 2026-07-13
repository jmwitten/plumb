"""``detailgen.incremental`` — revision identity across time (AD#7.5).

The single question this subsystem answers: *what does an edit to a detail
persist, move, resize, remove, or add* — instead of rebuilding a fresh,
anonymous model every time (see ``.superpowers/sdd/incr-design.md``).

This package is read-only over the existing ``compile_spec → validate →
evidence_graph`` pipeline. Its first piece is the **identity comparison
fingerprint** (:mod:`detailgen.incremental.identity_fingerprint`): a
per-member content signature, R17-immune by pre-rounding, that keeps the
transform component separate from the content component so a later revision
diff can distinguish *moved* from *resized*.
"""
