import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

import db
from assessment.service import discard_unscreened_free_text
from applicant.router import router as applicant_router
from applicant.schemas import FieldError, ValidationErrorResponse
from compliance.router import router as compliance_router
from employee.router import router as employee_router

DESCRIPTION = """
Prototype API for a care credit online intake: medical treatment financing of €500–25,000,
repaid over 6–60 months.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    discard_unscreened_free_text()
    if not os.environ.get("GROQ_API_KEY"):
        logging.getLogger("uvicorn.error").warning(
            "GROQ_API_KEY is not set: free-text screening is stubbed. Add your own key to backend/.env "
            "and start with --env-file .env to use the real model."
        )
    yield


app = FastAPI(
    title="care credit intake API",
    version="0.1.0",
    description=DESCRIPTION,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Applicant intake", "description": "The form the applicant fills in and its submissions."},
        {"name": "Employee", "description": "Reviewing applications and recording decisions."},
        {"name": "Compliance", "description": "Record keeping and retention."},
    ],
    swagger_ui_parameters={"displayRequestDuration": True, "tryItOutEnabled": True, "defaultModelsExpandDepth": 0},
)
app.include_router(applicant_router)
app.include_router(employee_router)
app.include_router(compliance_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Flatten Pydantic errors into {field, message} pairs a form can show next to each input."""
    errors = []
    for err in exc.errors():
        loc = [str(part) for part in err["loc"] if part != "body"]
        message = err["msg"]
        if err["type"] == "value_error":
            message = str(err["ctx"]["error"])
        elif err["type"] == "string_pattern_mismatch":
            message = "Please use digits only."
        elif err["type"] in ("missing", "string_too_short"):
            message = "Please fill this in."
        elif err["type"] == "string_type":
            message = 'Please send this as text in quotes, e.g. "123456789".'
        elif err["type"] == "int_type":
            message = "Please enter a whole number (no decimals, no text)."
        elif err["type"] in ("greater_than_equal", "less_than_equal"):
            ctx = err.get("ctx", {})
            bound = ctx.get("ge", ctx.get("le"))
            message = f"Must be {'at least' if 'ge' in ctx else 'at most'} {bound}."
        errors.append(FieldError(field=".".join(loc) or None, message=message))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ValidationErrorResponse(errors=errors).model_dump(),
    )

