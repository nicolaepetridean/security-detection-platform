"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import Base, engine
from .errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from .routers import auth, customers, detections, ingest, signatures

# Map each domain error to an HTTP status. Translation happens here, at the edge, so the
# service layer never imports HTTP concerns.
_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Refuse to boot with an insecure JWT secret outside development.
    settings.validate()
    # Create tables if they don't exist. For a simple assignment this replaces a full
    # migration tool (Alembic); noted as a limitation in the README.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Detection Management Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def _domain_error_handler(_: Request, exc: DomainError):
    code = _ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=code, content={"detail": exc.message})


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(signatures.router)
app.include_router(detections.router)
app.include_router(ingest.router)
