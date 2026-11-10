"""生成应用图标：圆角方块 + 2×2 方格（右下角高亮）。

输出 assets/icon.ico（16~256 多尺寸）和 assets/icon.png（512）。
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets"
SIZE = 1024
SS = 2  # 超采样倍数

TOP = (104, 143, 255)
MID = (61, 90, 240)
BOTTOM = (35, 45, 168)
MINT = (111, 227, 206)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def diagonal_gradient(size):
    """竖向渐变 + 左上柔光，逐像素算，避免出现硬边和色带。"""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        ty = y / max(1, size - 1)
        base = lerp(TOP, MID, ty / 0.6) if ty < 0.6 else lerp(MID, BOTTOM, (ty - 0.6) / 0.4)
        for x in range(size):
            tx = x / max(1, size - 1)
            dist = ((tx - 0.28) ** 2 + (ty - 0.16) ** 2) ** 0.5
            glow = max(0.0, 1 - dist / 0.85) ** 2 * 0.22
            color = tuple(min(255, round(c + (255 - c) * glow)) for c in base)
            px[x, y] = color
    return img


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def build(size):
    s = size * SS
    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    gradient = diagonal_gradient(s)
    mask = rounded_mask(s, radius=int(s * 0.255))
    base.paste(gradient, (0, 0), mask)

    # 2×2 方格
    margin = s * 0.215
    gap = s * 0.048
    cell = (s - margin * 2 - gap) / 2
    radius = cell * 0.30
    squares = [
        (margin, margin, 255),
        (margin + cell + gap, margin, 242),
        (margin, margin + cell + gap, 242),
        (margin + cell + gap, margin + cell + gap, "mint"),
    ]
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x, y, tone in squares:
        box = [x, y, x + cell, y + cell]
        if tone == "mint":
            fill = (*MINT, 255)
        else:
            fill = (255, 255, 255, tone)
        draw.rounded_rectangle(box, radius=radius, fill=fill)
    base = Image.alpha_composite(base, layer)

    return base.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = [256, 128, 64, 48, 32, 24, 16]
    images = {size: build(size) for size in sizes}

    master = images[256]
    master.save(OUT / "icon.png")

    # 用 256 作为基图，PIL 会按 sizes 逐级生成内嵌尺寸
    master.save(OUT / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes])

    for size, img in images.items():
        img.save(OUT / f"preview-{size}.png")
    print("icon.ico", (OUT / "icon.ico").stat().st_size, "bytes")
    print("icon.png", (OUT / "icon.png").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
