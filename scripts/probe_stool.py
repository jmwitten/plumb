"""Compile a stool sketch spec and print each part's world bbox + build/validation.

Usage: PYTHONPATH=$WT/.shim python scripts/probe_stool.py details/step_stool_X.spec.yaml
"""
import sys
from pathlib import Path
from detailgen.spec.compiler import compile_spec_file

spec = Path(sys.argv[1])
d = compile_spec_file(spec)
d.build()
print(f"=== {spec.name} : {len(d.assembly.parts)} parts ===")
for p in d.assembly.parts:
    bb = p.world_solid().val().BoundingBox()
    IN = 25.4
    print(f"  {p.name:22s}  X[{bb.xmin/IN:6.2f},{bb.xmax/IN:6.2f}] "
          f"Y[{bb.ymin/IN:6.2f},{bb.ymax/IN:6.2f}] Z[{bb.zmin/IN:6.2f},{bb.zmax/IN:6.2f}]")
try:
    rep = d.validate()
    print("validation:", str(rep))
    for f in rep.failures:
        print("  FAIL:", f)
    for f in rep.unresolved:
        print("  UNKNOWN:", f)
except Exception as e:
    import traceback; traceback.print_exc()
    print("validation error:", type(e).__name__, e)
