from detailgen.package.documents import (
    render_fabrication_html,
    render_installation_html,
    render_technical_html,
    write_package_documents,
)


def _document_inputs():
    technical = {
        "title": "Example <Assembly>",
        "headline": "Geometry PASS · Structural capacity UNKNOWN — NOT ANALYZED",
        "views": ("iso.png",),
        "coverage": (),
        "bom": (),
        "callouts": (),
    }
    fabrication = (
        {
            "part_id": "a",
            "part_name": "Part A",
            "stock_profile": "stock",
            "steps": (),
            "note": "purchased as-is",
        },
    )
    installation = {
        "installs": (),
        "event_graph": None,
        "connection_edges": (),
        "coverage": (),
    }
    return technical, fabrication, installation


def test_generic_documents_are_standalone_escaped_and_keep_unknowns():
    technical_data, fabrication_data, installation_data = _document_inputs()

    technical = render_technical_html(technical_data)
    fabrication = render_fabrication_html(fabrication_data)
    installation = render_installation_html(installation_data)

    assert "Example &lt;Assembly&gt;" in technical
    assert "UNKNOWN — NOT ANALYZED" in technical
    assert "Part A" in fabrication
    assert "No modeled installation contract" in installation
    assert all(text.startswith("<!doctype html>") for text in (
        technical,
        fabrication,
        installation,
    ))
    combined = (technical + fabrication + installation).lower()
    assert "armchair" not in combined
    assert "birdhouse" not in combined


def test_write_package_documents_creates_fixed_generic_surface(tmp_path):
    technical, fabrication, installation = _document_inputs()

    paths = write_package_documents(
        tmp_path,
        technical=technical,
        fabrication=fabrication,
        installation=installation,
    )

    assert paths == {
        "technical": tmp_path / "technical.html",
        "fabrication": tmp_path / "fabrication.html",
        "installation": tmp_path / "installation.html",
    }
    assert all(path.read_text(encoding="utf-8").startswith("<!doctype html>")
               for path in paths.values())
