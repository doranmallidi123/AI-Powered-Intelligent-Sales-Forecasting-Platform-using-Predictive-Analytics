"""FastAPI application entry point for SalesGenie AI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.leads import router as leads_router

app = FastAPI(title="SalesGenie AI API", version="1.0.0")
app.include_router(leads_router)

# Streamlit is normally served from :8501. The regex also permits other local
# development ports without opening cross-origin access to remote hosts.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a lightweight liveness response."""
    return {"status": "healthy", "service": "SalesGenie API"}


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Report database failures without exposing connection details."""
    return JSONResponse(
        status_code=503,
        content={"detail": "Database service is temporarily unavailable."},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return FastAPI request validation details in a stable envelope."""
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors raised outside request parsing."""
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
