import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .infrai_email import InfraiEmail, InfraiError
from .report_delivery import ReportDelivery
from .report_models import ReportAccepted, ReportRequest

REPORT_DIR = Path(os.environ.get("REPORT_DIR", "var/reports"))
REPORT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Developer-tools release reports")
app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")


@app.post("/release-reports", response_model=ReportAccepted, status_code=202)
def create_release_report(request: ReportRequest) -> ReportAccepted:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    email = InfraiEmail(api_key)
    try:
        return ReportDelivery(email, REPORT_DIR, public_base_url).deliver(request)
    except InfraiError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.detail.get("message")},
        ) from exc
    finally:
        email.close()


def run() -> None:
    uvicorn.run("devtools_reporter.service:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()

