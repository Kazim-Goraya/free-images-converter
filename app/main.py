import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from .converter import SUPPORTED_FORMATS, prepare_image, write_pdf

MAX_FILES = 200
MAX_FILE_MB = 100
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Images to PDF")


def save_uploads(files: list[UploadFile], folder: Path) -> list[tuple[str, Path]]:
    """Stream uploads to disk (safe names, size-capped). Keeps the client's order."""
    folder.mkdir(parents=True, exist_ok=True)
    items = []
    for i, up in enumerate(files):
        name = Path(up.filename or f"image{i}").name
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise HTTPException(415, f"Unsupported file type: {name}")
        dest, size = folder / f"{i:04d}{ext}", 0
        with open(dest, "wb") as out:
            while chunk := up.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_MB * 1024 * 1024:
                    raise HTTPException(413, f"{name} is larger than {MAX_FILE_MB} MB")
                out.write(chunk)
        items.append((name, dest))
    return items


def prepare_all(items, norm_dir: Path) -> list[str]:
    ready = []
    for name, path in items:
        try:
            ready.append(prepare_image(path, norm_dir))
        except Exception:
            raise HTTPException(422, f"'{name}' is not a valid image")
    return ready


@app.post("/api/convert")
def convert(
    files: list[UploadFile] = File(...),
    mode: str = Form("single"),     # single | separate
    page: str = Form("original"),   # original | a4
    dpi: int = Form(300),
):
    if not files:
        raise HTTPException(400, "No files uploaded")
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"Maximum {MAX_FILES} images per request")
    if mode not in ("single", "separate") or page not in ("original", "a4"):
        raise HTTPException(400, "Invalid options")
    dpi, a4 = max(72, min(dpi, 600)), page == "a4"

    work = Path(tempfile.mkdtemp(prefix="img2pdf_"))
    try:
        items = save_uploads(files, work / "in")
        sources = prepare_all(items, work / "norm")
        out_dir = work / "out"
        out_dir.mkdir()

        if mode == "single" or len(items) == 1:
            result = out_dir / "images.pdf"
            write_pdf(sources, result, a4, dpi)
            media = "application/pdf"
        else:
            result, used = out_dir / "pdfs.zip", set()
            with zipfile.ZipFile(result, "w", zipfile.ZIP_STORED) as zf:
                for (name, _), src in zip(items, sources):
                    stem = re.sub(r"[^\w.\- ]", "_", Path(name).stem) or "image"
                    pdf_name, n = f"{stem}.pdf", 1
                    while pdf_name.lower() in used:
                        n += 1
                        pdf_name = f"{stem}_{n}.pdf"
                    used.add(pdf_name.lower())
                    tmp_pdf = out_dir / f"{len(used)}.pdf"
                    write_pdf([src], tmp_pdf, a4, dpi)
                    zf.write(tmp_pdf, pdf_name)
                    tmp_pdf.unlink()
            media = "application/zip"

        return FileResponse(result, media_type=media, filename=result.name,
                            background=BackgroundTask(shutil.rmtree, work, ignore_errors=True))
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise


# Must come last so it doesn't shadow /api routes
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
