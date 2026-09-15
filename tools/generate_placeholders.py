#!/usr/bin/env python3
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hatenadir" / "images" / "ds"


def ntft_bytes(image):
    import sys
    sys.path.insert(0, str(ROOT))
    from reximemo_image_formats import encode_image
    return encode_image(image.convert("RGBA"), "ntft").data


def npf_bytes(image):
    import sys
    sys.path.insert(0, str(ROOT))
    from reximemo_image_formats import encode_image
    return encode_image(image.convert("RGBA"), "npf").data


def icon(kind):
    im = Image.new("RGBA", (32, 32), (226, 216, 235, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((2, 2, 29, 29), outline=(93, 69, 112, 255), width=2)
    if kind == "browse":
        for y in (8, 15, 22):
            d.rectangle((7, y, 24, y + 3), fill=(111, 145, 41, 255))
    elif kind == "account":
        d.ellipse((11, 6, 20, 15), fill=(111, 145, 41, 255))
        d.rectangle((8, 17, 23, 25), fill=(111, 145, 41, 255))
    else:
        d.rectangle((7, 11, 24, 25), fill=(111, 145, 41, 255))
        d.polygon(((6, 12), (16, 5), (25, 12)), fill=(93, 69, 112, 255))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("browse", "account", "room"):
        (OUT / f"{name}.ntft").write_bytes(ntft_bytes(icon(name)))
    banner = Image.new("RGBA", (128, 64), (226, 216, 235, 255))
    d = ImageDraw.Draw(banner)
    d.rectangle((4, 4, 123, 59), outline=(93, 69, 112, 255), width=3)
    d.rectangle((18, 22, 110, 42), fill=(111, 145, 41, 255))
    (OUT / "placeholder.npf").write_bytes(npf_bytes(banner))


if __name__ == "__main__":
    main()
