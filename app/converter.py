"""Lossless image -> PDF conversion (img2pdf + Pillow). No web code here."""
from pathlib import Path

import img2pdf
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PURE_ROTATIONS = {None, 1, 3, 6, 8}

def prepare_image(path: Path, norm_dir: Path) -> str:
    """Return a path img2pdf can embed without quality loss (original if possible)."""
    with Image.open(path) as im:
        orientation = im.getexif().get(0x0112)
        if im.format in ("JPEG", "PNG") and im.mode in ("RGB", "L") \
                and orientation in PURE_ROTATIONS:
            return str(path)

        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            flat = Image.new("RGB", rgba.size, "white")
            flat.paste(rgba, mask=rgba.getchannel("A"))
            im = flat
        elif im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        norm_dir.mkdir(parents=True, exist_ok=True)
        out = norm_dir / f"{path.stem}.png"
        im.save(out, "PNG", compress_level=6)
        return str(out)


def make_layout(a4: bool, dpi: int):
    if a4:  # fit inside A4 with 10 mm margin, auto landscape for wide images
        m = img2pdf.mm_to_pt(10)
        return img2pdf.get_layout_fun(
            pagesize=(img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297)),
            border=(m, m), fit=img2pdf.FitMode.into, auto_orient=True,
        )
    return img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))  # page = image size


def write_pdf(sources: list[str], out_pdf: Path, a4: bool = False, dpi: int = 300) -> None:
    with open(out_pdf, "wb") as fh:
        img2pdf.convert(sources, layout_fun=make_layout(a4, dpi), outputstream=fh)
