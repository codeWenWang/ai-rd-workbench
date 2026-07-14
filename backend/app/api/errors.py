from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError, ResourceNotFound, ValidationError


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = 404 if isinstance(exc, ResourceNotFound) else 422 if isinstance(exc, ValidationError) else 503
    return JSONResponse(status_code=status, content={"code": exc.code, "message": exc.message,
                        "request_id": request.headers.get("x-request-id") or str(uuid4()),
                        "details": exc.details})


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": "internal_error",
                        "message": "Internal server error",
                        "request_id": request.headers.get("x-request-id") or str(uuid4()),
                        "details": None})
