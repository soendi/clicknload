"""Generates icon.ico from arrow.png with green + red variants (16-256px)."""
from PIL import Image
import struct, io

src = Image.open("arrow.png").convert("RGBA")

def colorize(color):
    out = Image.new("RGBA", src.size)
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = src.getpixel((x, y))
            if a > 0:
                out.putpixel((x, y), (*color, a))
    return out

GREEN = (46, 204, 113)
RED   = (231, 76, 60)
sizes = [16, 24, 32, 48, 64, 128, 256]

def build_ico(image, path):
    """Build ICO file with multiple sizes (manual structure)."""
    frames = [image.resize((s, s), Image.LANCZOS) for s in sizes]
    # Encode each frame as PNG (for modern ICO)
    png_data = []
    for f in frames:
        buf = io.BytesIO()
        f.save(buf, format="PNG")
        png_data.append(buf.getvalue())
    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    # Directory entries: each is 16 bytes
    dir_entries = b""
    offset = 6 + len(sizes) * 16
    for i, (s, png) in enumerate(zip(sizes, png_data)):
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        bpp = 32
        size = len(png)
        dir_entries += struct.pack("<BBBBHHII", w, h, 1, 0, 1, bpp, size, offset)
        offset += size
    with open(path, "wb") as f:
        f.write(header + dir_entries)
        for png in png_data:
            f.write(png)
    print(f"{path}: {len(sizes)} Grössen, {offset} Bytes")

build_ico(colorize(GREEN), "icon.ico")
build_ico(colorize(RED), "icon_red.ico")
print("Fertig.")
