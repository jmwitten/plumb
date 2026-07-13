"""detailgen — parametric construction details built on CadQuery.

Package layout:
    detailgen.core        base Component class, units, materials
    detailgen.components  primitive parts: lumber, concrete, fasteners, connectors
    detailgen.assemblies  DetailAssembly: positioning, coloring, BOM
    detailgen.validation  geometric checks (clearance, intersection, dimensions)
    detailgen.rendering   STEP / STL / PNG export

Importing this top-level package eagerly imports every subpackage whose
defining modules populate the roadmap-item-8 registries
(``detailgen.core.registry``: components, materials, exporters, checks) —
requirement 4 of that task: ``import detailgen`` alone is enough to see the
full vocabulary in each registry, with no extra ceremony beyond what a
detail script already does (every detail imports these same subpackages
directly). Order matters only in that each subpackage below is
self-contained via its own relative imports; this list itself doesn't
need to be dependency-sorted.
"""

__version__ = "0.1.0"

from . import core  # noqa: F401,E402
from . import components  # noqa: F401,E402
from . import assemblies  # noqa: F401,E402
from . import validation  # noqa: F401,E402
from . import rendering  # noqa: F401,E402
