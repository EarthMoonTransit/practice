from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from . import db, model, report

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
REPORT_PATH = DATA_DIR / "report.pdf"

MAX_FILE_MB = 20
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Fruit Counter")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


def _build_context(
    result: Optional[Dict] = None, error: Optional[str] = None, load_model_info: bool = False
) -> Dict:
    summary = db.get_summary()
    counts_by_class = db.get_counts_by_class()
    recent = db.fetch_recent(limit=10)
    return {
        "summary": summary,
        "counts_by_class": counts_by_class,
        "recent": recent,
        "result": result,
        "error": error,
        "supported_fruits": ", ".join(model.get_supported_fruits(allow_load=load_model_info)),
        "max_file_mb": MAX_FILE_MB,
        "allowed_ext": ", ".join(sorted(ALLOWED_EXTENSIONS)),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    context = _build_context(load_model_info=False)
    context["request"] = request
    return templates.TemplateResponse("index.html", context)


@app.post("/process", response_class=HTMLResponse)
async def process_image(request: Request, image: UploadFile = File(...)) -> HTMLResponse:
    if image is None or image.filename is None:
        context = _build_context(error="Файл не выбран.", load_model_info=False)
        context["request"] = request
        return templates.TemplateResponse("index.html", context)

    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        context = _build_context(
            error=f"Неподдерживаемый тип файла. Разрешены: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
        context["request"] = request
        return templates.TemplateResponse("index.html", context)

    contents = await image.read()
    if len(contents) > MAX_FILE_MB * 1024 * 1024:
        context = _build_context(error=f"Файл слишком большой. Максимум {MAX_FILE_MB} МБ.")
        context["request"] = request
        return templates.TemplateResponse("index.html", context)

    file_id = uuid.uuid4().hex
    upload_path = UPLOAD_DIR / f"{file_id}{ext}"
    upload_path.write_bytes(contents)

    try:
        with Image.open(upload_path) as img:
            img.verify()
    except Exception:
        upload_path.unlink(missing_ok=True)
        context = _build_context(error="Загруженный файл не является корректным изображением.")
        context["request"] = request
        return templates.TemplateResponse("index.html", context)

    counts, total, annotated_image, processing_ms = model.run_detection(upload_path)
    output_filename = f"{file_id}_result.jpg"
    output_path = OUTPUT_DIR / output_filename
    annotated_image.save(output_path, format="JPEG", quality=90)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request_id = db.insert_request(
        filename=image.filename,
        output_path=output_filename,
        counts=counts,
        total_count=total,
        model_name=model.MODEL_NAME,
        created_at=created_at,
        processing_ms=processing_ms,
    )

    result = {
        "request_id": request_id,
        "original_name": image.filename,
        "output_url": f"/outputs/{output_filename}",
        "counts": counts,
        "total": total,
        "processing_ms": processing_ms,
        "created_at": created_at,
    }

    context = _build_context(result=result, load_model_info=True)
    context["request"] = request
    return templates.TemplateResponse("index.html", context)


@app.get("/report.pdf")
def get_report() -> FileResponse:
    report.generate_report(REPORT_PATH)
    return FileResponse(path=REPORT_PATH, filename="report.pdf")
