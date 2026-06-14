"""Render the 3-minute pitch script (pitch.html) to a PDF via headless Chromium."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE, "pitch.html"), encoding="utf-8").read()
out = os.path.join(HERE, "ScreenSmart_Pitch.pdf")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content(html, wait_until="networkidle")
    pg.pdf(path=out, format="A4", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("rendered", out)
