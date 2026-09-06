#!/usr/bin/env python3
"""Splices synthetic-data/frontend-data.json into frontend/app.template.html,
producing the final single-file prototype frontend/riskon.html.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
template = (ROOT / "frontend" / "app.template.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "synthetic-data" / "frontend-data.json").read_text(encoding="utf-8"))

data_js = "window.RISKON_DATA = " + json.dumps(data, separators=(",", ":")) + ";"
out = template.replace("/*__RISKON_DATA__*/", data_js)

assert "/*__RISKON_DATA__*/" not in out, "placeholder not replaced"

out_path = ROOT / "frontend" / "riskon.html"
out_path.write_text(out, encoding="utf-8")
print(f"Wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
