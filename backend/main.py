from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from error_codes import ERR_RATE_LIMITED
from lifespan import lifespan
from rate_limit import is_rate_limited
from routes.check import router as check_router
from routes.config import router as config_router
from routes.results import router as results_router
from routes.runtime import router as runtime_router
from routes.validation import router as validation_router
from settings import CORS_ORIGINS

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Report Checker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-ID"],
)


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/check":
        client_ip = request.client.host if request.client else "unknown"
        if is_rate_limited(client_ip):
            return JSONResponse(
                status_code=ERR_RATE_LIMITED.http_status,
                content={"detail": {"code": ERR_RATE_LIMITED.code, "message": ERR_RATE_LIMITED.message}},
            )
    return await call_next(request)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(config_router)
app.include_router(check_router)
app.include_router(results_router)
app.include_router(validation_router)
app.include_router(runtime_router)
