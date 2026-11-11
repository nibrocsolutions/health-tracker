from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.routes import router
from app.config import settings
from app.database import Base, engine, ensure_columns

STATIC_DIR = Path(__file__).resolve().parent / "static"


class FreshStaticFiles(StaticFiles):
    """Ask the phone to recheck scripts and styles after a rebuild."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "no-cache"
        return response


def index_html() -> str:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for asset in ("css/app.css", "js/app.js"):
        stamp = int((STATIC_DIR / asset).stat().st_mtime)
        html = html.replace(f"/static/{asset}", f"/static/{asset}?v={stamp}", 1)
    return html


def _plain_error(exc: RequestValidationError) -> str:
    messages = []
    for err in exc.errors():
        msg = str(err.get("msg") or "Check that entry.")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        if msg not in messages:
            messages.append(msg)
    return messages[0] if len(messages) == 1 else " ".join(messages)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
app.include_router(admin_router)
app.mount("/static", FreshStaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _plain_error(exc)})


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(index_html(), headers={"Cache-Control": "no-cache"})


@app.get("/admin")
@app.get("/admin/")
def admin_page() -> HTMLResponse:
    return HTMLResponse(index_html(), headers={"Cache-Control": "no-cache"})
