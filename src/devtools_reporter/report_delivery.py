import hashlib
import html
from pathlib import Path
from urllib.parse import quote

from .infrai_email import InfraiEmail
from .pdf_report import render_release_report
from .report_models import ReportAccepted, ReportRequest, decide_release


class ReportDelivery:
    def __init__(self, email: InfraiEmail, report_dir: Path, public_base_url: str) -> None:
        self._email = email
        self._report_dir = report_dir
        self._public_base_url = public_base_url.rstrip("/")

    def deliver(self, request: ReportRequest) -> ReportAccepted:
        decision = decide_release(request.events)
        release_id = request.operation.release_id
        report_name = f"{release_id}.pdf"
        render_release_report(request, decision, self._report_dir / report_name)
        report_url = f"{self._public_base_url}/reports/{quote(report_name)}"
        safe_url = html.escape(report_url, quote=True)
        subject = f"Release {release_id}: {decision.value}"
        body = (
            f"<h1>{html.escape(subject)}</h1>"
            f"<p>Your build diagnostics are ready.</p>"
            f'<p><a href="{safe_url}">Open the PDF report</a></p>'
        )
        key_material = f"release-report:{release_id}:{request.recipient}".encode()
        idempotency_key = hashlib.sha256(key_material).hexdigest()
        message_id = self._email.send_report(
            to=request.recipient,
            subject=subject,
            html=body,
            idempotency_key=idempotency_key,
        )
        return ReportAccepted(
            release_id=release_id,
            decision=decision,
            message_id=message_id,
            report_url=report_url,
        )

