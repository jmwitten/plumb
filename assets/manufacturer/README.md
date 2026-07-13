STEP files from manufacturers (Simpson Strong-Tie, USP, etc.).

Load them as placeable components with:

    from detailgen.assemblies import load_step
    hanger = load_step("assets/manufacturer/LUS28.step", name="LUS28")
