"""Render SVGs to high-res PNGs via headless Chromium (faithful emoji + gradients) for
embedding in the deck:
  - docs/architecture.svg            -> presentation/architecture.png
  - presentation/garaza_logo.svg     -> presentation/garaza_logo.png (recoloured for dark bg)
Run inside a container with playwright + chromium."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def render(svg_text, out, w, h, scale=2):
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0;background:transparent}"
        f"svg{{width:{w}px;height:{h}px;display:block}}</style></head>"
        f"<body>{svg_text}</body></html>"
    )
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg.set_content(html, wait_until="networkidle")
        el = pg.query_selector("svg")
        el.screenshot(path=out, omit_background=True)
        b.close()
    print("rendered", out)


# architecture diagram
arch = open(os.path.join(ROOT, "docs", "architecture.svg"), encoding="utf-8").read()
render(arch, os.path.join(HERE, "architecture.png"), 1320, 720)

# garaza logo — recolour the near-black wordmark to light, keep the purple accent
logo = open(os.path.join(HERE, "garaza_logo.svg"), encoding="utf-8").read()
logo = logo.replace('fill="#191919"', 'fill="#E8EDF6"')
render(logo, os.path.join(HERE, "garaza_logo.png"), 397, 92, scale=4)
