"""Draw the site's tab icons and the link-preview picture (issue #266).

Run from the repository root with a Python that has Pillow:

    python3 tools/make_site_images.py

Writes assets/favicon-32.png, assets/apple-touch-icon.png and
assets/og-preview.png. Development only: the app never imports this, and the
runtime image has no Pillow. The vector icon, assets/favicon.svg, is written
by hand and kept in step with the mark drawn here.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = ASSETS / "nunito-variable.ttf"

BACKGROUND = (20, 13, 9)       # --bg, night
GOLD = (244, 189, 56)          # --gold
GOLD_DEEP = (216, 145, 21)     # the mark's gradient end
MARK_INK = (42, 28, 16)        # the letters on the mark
INK = (255, 253, 248)          # --ink
MUTED = (201, 187, 171)        # --muted


def font(size: int, weight: int = 900) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size)
    face.set_variation_by_axes([weight])
    return face


def mark(size: int, scale: int = 4) -> Image.Image:
    """The yellow RJ mark: a rounded gold square with dark letters."""
    big = size * scale
    gradient = Image.new("RGB", (big, big))
    pixels = gradient.load()
    for y in range(big):
        for x in range(big):
            t = (x + y) / (2 * big - 2)
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(GOLD, GOLD_DEEP))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 0.26), fill=255)
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    tile.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(tile)
    draw.text((big / 2, big / 2), "RJ", font=font(round(big * 0.5)), fill=MARK_INK, anchor="mm")
    return tile.resize((size, size), Image.LANCZOS)


def preview() -> Image.Image:
    """1200x630, the size messaging apps expect: the sign-in screen in brief."""
    width, height = 1200, 630
    card = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(card)
    tile = mark(132)
    card.paste(tile, ((width - 132) // 2, 78), tile)
    draw.text((width / 2, 282), "Sort Quiz", font=font(88), fill=INK, anchor="mm")
    draw.text(
        (width / 2, 362),
        "Learn the chart. Play Ranked. Climb the leaderboard.",
        font=font(34, 600), fill=MUTED, anchor="mm",
    )
    button = (330, 430, 870, 518)
    draw.rounded_rectangle(button, radius=22, fill=GOLD)
    draw.text((width / 2, 474), "Log in with Quiz Code", font=font(36), fill=MARK_INK, anchor="mm")
    draw.text((width / 2, 574), "sortquiz.app", font=font(26, 700), fill=MUTED, anchor="mm")
    return card


def main() -> None:
    mark(32, scale=8).save(ASSETS / "favicon-32.png", optimize=True)
    # iOS paints transparent corners black and rounds the icon itself, so the
    # home-screen icon is the mark on the app's own background, full bleed.
    touch = Image.new("RGB", (180, 180), BACKGROUND)
    tile = mark(140)
    touch.paste(tile, (20, 20), tile)
    touch.save(ASSETS / "apple-touch-icon.png", optimize=True)
    preview().save(ASSETS / "og-preview.png", optimize=True)


if __name__ == "__main__":
    main()
