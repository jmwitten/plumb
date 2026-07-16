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
.table-scroll{{overflow-x:auto;max-width:100%;border:1px solid #cbd5e1}}
.table-scroll table{{width:max-content;min-width:100%;margin:0}}
.table-scroll th,.table-scroll td{{border-width:0 1px 1px 0}}
.table-scroll-cue{{display:none;margin:0 0 6px;color:#475569;font-size:13px}}
img{{max-width:100%;height:auto}}
.unknown{{border-left:5px solid #b45309;padding:10px;background:#fff7ed}}
section{{margin:28px 0}}
@media(max-width:640px){{body{{padding:20px 16px}}.table-scroll-cue{{display:block}}}}
@media print{{body{{padding:0}}.table-scroll{{overflow:visible;border:0}}.table-scroll table{{width:100%;min-width:0;font-size:9pt}}.table-scroll-cue{{display:none}}}}
</style>
</head><body>{body}</body></html>"""
