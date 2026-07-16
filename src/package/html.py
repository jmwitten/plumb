"""Small shared HTML shell for generated contractor documents."""

from html import escape


def page(title: str, body: str) -> str:
    """Wrap already-rendered body HTML in a standalone printable page."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{max-width:960px;margin:auto;padding:32px;font:15px/1.5 system-ui;color:#172033}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}}
img{{max-width:100%;height:auto}}
.unknown{{border-left:5px solid #b45309;padding:10px;background:#fff7ed}}
section{{margin:28px 0}}
@media print{{body{{padding:0}}}}
</style>
</head><body>{body}</body></html>"""
