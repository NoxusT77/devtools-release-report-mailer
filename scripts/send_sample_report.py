import json
import os
from datetime import datetime, timezone
from pathlib import Path

from devtools_reporter.infrai_email import InfraiEmail
from devtools_reporter.report_delivery import ReportDelivery
from devtools_reporter.report_models import BuildEvent, BuildState, ReleaseOperation, ReportRequest


def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    recipient = os.environ.get("REPORT_RECIPIENT")
    if not api_key or not recipient:
        raise SystemExit("Set INFRAI_API_KEY and REPORT_RECIPIENT")

    request = ReportRequest(
        recipient=recipient,
        operation=ReleaseOperation(
            release_id="editor-2026-09-19",
            commit_sha="1a2b3c4d",
            environment="staging",
            started_at=datetime.now(timezone.utc),
        ),
        events=[
            BuildEvent(
                check="media-render-tests",
                state=BuildState.PASSED,
                duration_seconds=42.8,
                detail="Thumbnail and caption fixtures matched.",
            ),
            BuildEvent(
                check="creator-api-contract",
                state=BuildState.PASSED,
                duration_seconds=8.4,
                detail="Publish request contract passed.",
            ),
        ],
    )
    client = InfraiEmail(api_key)
    try:
        result = ReportDelivery(
            client,
            Path(os.environ.get("REPORT_DIR", "var/reports")),
            os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000"),
        ).deliver(request)
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()

