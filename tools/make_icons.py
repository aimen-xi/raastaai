"""Generate the RaastaAI app icon (asphalt square, yellow lane dashes, small pin) for web + Android.

Usage: python tools/make_icons.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASPHALT, YELLOW, ORANGE = (31, 41, 51), (245, 183, 0), (194, 65, 12)


def icon(size: int, maskable=False, rounded=True) -> Image.Image:
    s = 4 * size  # draw big, downsample for smooth edges
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded and not maskable:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=ASPHALT)
    else:
        d.rectangle([0, 0, s, s], fill=ASPHALT)
    pad = 0.2 if maskable else 0.12  # maskable icons need a safe zone
    inner = s * (1 - 2 * pad)
    x0 = s * pad
    # three lane dashes, left of centre
    w, h, gap = inner * 0.14, inner * 0.22, inner * 0.17
    cx = x0 + inner * 0.36
    y = s * pad + (inner - (3 * h + 2 * gap)) / 2
    for _ in range(3):
        d.rounded_rectangle([cx - w / 2, y, cx + w / 2, y + h], radius=w * 0.15, fill=YELLOW)
        y += h + gap
    # location pin, right
    px, py, r = x0 + inner * 0.72, s * pad + inner * 0.42, inner * 0.17
    d.polygon([(px - r * 0.86, py + r * 0.5), (px + r * 0.86, py + r * 0.5), (px, py + r * 2.1)], fill=ORANGE)
    d.ellipse([px - r, py - r, px + r, py + r], fill=ORANGE)
    d.ellipse([px - r * 0.42, py - r * 0.42, px + r * 0.42, py + r * 0.42], fill=ASPHALT)
    return im.resize((size, size), Image.LANCZOS)


def main():
    web = os.path.join(ROOT, "app", "web")
    icon(192).save(os.path.join(web, "icons", "Icon-192.png"))
    icon(512).save(os.path.join(web, "icons", "Icon-512.png"))
    icon(192, maskable=True).save(os.path.join(web, "icons", "Icon-maskable-192.png"))
    icon(512, maskable=True).save(os.path.join(web, "icons", "Icon-maskable-512.png"))
    icon(180, rounded=False).convert("RGB").save(os.path.join(web, "icons", "apple-touch-icon.png"))  # iOS rounds it
    icon(32).save(os.path.join(web, "favicon.png"))
    res = os.path.join(ROOT, "app", "android", "app", "src", "main", "res")
    for folder, px in {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96, "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}.items():
        p = os.path.join(res, folder)
        if os.path.isdir(p):
            icon(px).save(os.path.join(p, "ic_launcher.png"))
    print("icons written")


if __name__ == "__main__":
    main()
