"""
setup_favicon.py
----------------
Generates the favicon assets for cslassiter.github.io and injects the
favicon <link> tags into every page.

Design: a "CL" monogram on the site's navy (#1a1a2e) ground, cream serif
letters (#f4f3ef), and the signature dark-red (#8B0000) accent bar across
the bottom -- the same bar used on the header and every content card.

Outputs (written to the repo root):
  - favicon.svg          scalable, used by modern browsers
  - favicon.ico          multi-size (16/32/48), legacy + broad support
  - apple-touch-icon.png 180x180, iOS home-screen icon

Also inserts, after the <meta charset> line of every *.html file:
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

Requires: Pillow (pip install Pillow)
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

NAVY = (26, 26, 46)      # #1a1a2e
CREAM = (244, 243, 239)  # #f4f3ef
RED = (139, 0, 0)        # #8B0000
TEXT = "CL"

# ---------------------------------------------------------------- SVG --------
SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="Charles Lassiter">
  <defs>
    <clipPath id="rounded"><rect width="64" height="64" rx="9"/></clipPath>
  </defs>
  <g clip-path="url(#rounded)">
    <rect width="64" height="64" fill="#1a1a2e"/>
    <text x="32" y="42" text-anchor="middle"
          font-family="Georgia, 'Times New Roman', serif"
          font-weight="600" font-size="36" fill="#f4f3ef">CL</text>
    <rect x="0" y="55" width="64" height="9" fill="#8B0000"/>
  </g>
</svg>
"""


def load_serif(size):
    """Best available serif on Windows, heavy enough to read at 16px."""
    for name in ("georgiab.ttf", "timesbd.ttf", "georgia.ttf", "times.ttf"):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def draw_icon(px, rounded=True):
    """Render the monogram at `px` pixels (supersampled 4x, then downscaled)."""
    s = px * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(s * 9 / 64) if rounded else 0

    # navy ground
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=NAVY)

    # dark-red accent bar across the bottom (clipped to the rounded ground)
    bar_top = int(s * 55 / 64)
    bar = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rectangle([0, bar_top, s - 1, s - 1], fill=RED)
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.paste(bar, (0, 0), Image.composite(bar.split()[3], Image.new("L", (s, s), 0), mask))

    # CL monogram, optically centred in the space above the bar
    font = load_serif(int(s * 36 / 64))
    cx = s // 2
    cy = int(bar_top * 0.5) + int(s * 0.5 / 64)
    d.text((cx, cy), TEXT, font=font, fill=CREAM, anchor="mm")

    return img.resize((px, px), Image.LANCZOS)


def build_assets():
    (ROOT / "favicon.svg").write_text(SVG, encoding="utf-8")
    print("wrote favicon.svg")

    ico = draw_icon(64, rounded=True)
    ico.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico (16/32/48)")

    apple = draw_icon(180, rounded=False)          # iOS rounds it itself
    apple.convert("RGB").save(ROOT / "apple-touch-icon.png")
    print("wrote apple-touch-icon.png (180x180)")


# --------------------------------------------------------------- HTML --------
LINKS = [
    '<link rel="icon" href="/favicon.ico" sizes="any">',
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
]


def inject_links():
    changed = 0
    for html in sorted(ROOT.rglob("*.html")):
        text = html.read_text(encoding="utf-8")
        if 'rel="icon"' in text:
            continue  # already has a favicon -> idempotent
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if "<meta charset" in line.lower():
                indent = line[: len(line) - len(line.lstrip())]
                nl = "\n" if line.endswith("\n") else ""
                block = "".join(f"{indent}{l}{nl}" for l in LINKS)
                lines.insert(i + 1, block)
                html.write_text("".join(lines), encoding="utf-8")
                changed += 1
                print(f"updated {html.relative_to(ROOT)}")
                break
    print(f"\n{changed} HTML file(s) updated")


if __name__ == "__main__":
    build_assets()
    inject_links()
