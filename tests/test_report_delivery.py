from datetime import datetime, timezone
from pathlib import Path

from devtools_reporter.report_delivery import ReportDelivery
from devtools_reporter.report_models import BuildEvent, BuildState, ReleaseOperation, ReportRequest


class RecordingEmail:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    def send_report(self, *, to: str, subject: str, html: str, idempotency_key: str) -> str:
        self.sent = {
            "to": to,
            "subject": subject,
            "html": html,
            "idempotency_key": idempotency_key,
        }
        return "msg_report_42"


def test_failed_check_blocks_release_and_emails_pdf(tmp_path: Path) -> None:
    request = ReportRequest(
        recipient="builder@example.com",
        operation=ReleaseOperation(
            release_id="studio-184",
            commit_sha="abc1234",
            environment="production",
            started_at=datetime(2026, 9, 19, 9, 30, tzinfo=timezone.utc),
        ),
        events=[
            BuildEvent(
                check="unit-tests",
                state=BuildState.PASSED,
                duration_seconds=12.1,
                detail="All editor tests passed.",
            ),
            BuildEvent(
                check="video-export",
                state=BuildState.FAILED,
                duration_seconds=31.7,
                detail="Expected H.264 fixture was absent.",
            ),
        ],
    )
    email = RecordingEmail()

    result = ReportDelivery(email, tmp_path, "https://reports.example.com").deliver(request)

    assert result.decision == "blocked"
    assert result.message_id == "msg_report_42"
    assert email.sent["subject"] == "Release studio-184: blocked"
    assert email.sent["to"] == "builder@example.com"
    assert result.report_url in email.sent["html"]
    assert (tmp_path / "studio-184.pdf").read_bytes().startswith(b"%PDF")

