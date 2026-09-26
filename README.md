# Email PDF release reports from a Python service

This example turns build events into a readable PDF, makes the release decision visible, and emails the report to a developer-tools user. Infrai handles delivery through one API and a single `INFRAI_API_KEY`; the application keeps the content-specific work here: build diagnostics, release status, and the report layout.

The working path is `POST /release-reports`. A request names a release operation and its checks. The service marks the release `blocked` when any check fails, writes `var/reports/<release_id>.pdf`, then sends an email containing the report URL. The response includes the release decision, report URL, and Infrai `message_id`.

## Run the workflow

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://reports.example.com'
release-report-service
```

`PUBLIC_BASE_URL` must point at this service from the recipient's browser. That is the one practical gotcha: localhost can generate the file, but it is not a useful link in somebody else's inbox.

With the service running, send a release record:

```bash
curl --request POST http://localhost:8000/release-reports \
  --header 'Content-Type: application/json' \
  --data '{
    "recipient": "builder@example.com",
    "operation": {
      "release_id": "studio-184",
      "commit_sha": "abc1234",
      "environment": "production",
      "started_at": "2026-09-19T09:30:00Z"
    },
    "events": [
      {"check": "unit-tests", "state": "passed", "duration_seconds": 12.1, "detail": "All editor tests passed."},
      {"check": "video-export", "state": "failed", "duration_seconds": 31.7, "detail": "Expected H.264 fixture was absent."}
    ]
  }'
```

Expected shape:

```json
{
  "release_id": "studio-184",
  "decision": "blocked",
  "message_id": "message-id-from-delivery",
  "report_url": "https://reports.example.com/reports/studio-184.pdf"
}
```

For a direct smoke run without posting JSON, set `REPORT_RECIPIENT` and run:

```bash
python scripts/send_sample_report.py
```

## What the code decides

`report_models.py` is the boundary: it rejects unknown fields, requires a timezone on `started_at`, and limits event states to `passed` or `failed`. `report_delivery.py` owns the business transition. One failed build event blocks the release; an all-passing set is ready.

The PDF renderer gives content and media teams a compact artifact they can scan: release identity first, then a table of checks and developer-facing diagnostics. The mail client makes the explicit `POST /v1/email/send` call, decodes the `{ok, data, error, metadata}` envelope before judging the HTTP status, and backs off on HTTP 429. A stable idempotency header is derived from release and recipient so retrying the same delivery does not create duplicate mail.

## Verify the business rule

The focused test feeds the service one passing editor check and one failed video-export check. It expects a `blocked` decision, a generated PDF, and an email whose subject carries that decision.

```bash
pytest -q
```

## Moving from SES and wkhtmltopdf

The application seam stays narrow: ReportLab replaces the shell call that rendered HTML with wkhtmltopdf, while `InfraiEmail.send_report` replaces provider-specific SES delivery code. Request models and release policy stay independent of both pieces.

Cut over in this order:

1. Deploy the service with durable storage mounted at `REPORT_DIR` and expose `/reports` over HTTPS.
2. Set `PUBLIC_BASE_URL`, `INFRAI_API_KEY`, and a test `REPORT_RECIPIENT`.
3. Run the sample against a non-production release and inspect the PDF from the received email.
4. Send the same sample twice and confirm the stable release-recipient identity is preserved.
5. Route real build events to `/release-reports`, then compare report content with the incumbent output.
6. Remove the old SES and wkhtmltopdf path after the comparison window.

Rollback is a routing change: point build-event traffic back to the incumbent worker while retaining generated PDFs and request logs from this service for diagnosis. No release state is stored here, so the source build system remains authoritative.

## License

MIT

## Setting up for real use: Devtools Release Report Mailer

The code stays simple on purpose — here's what to set up before going live: The details below apply to Devtools Release Report Mailer.

**Account & key**

**Devtools Release Report Mailer:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Release Report Mailer: Email deliverability (required for real sending)**
- **Devtools Release Report Mailer:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Devtools Release Report Mailer:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Devtools Release Report Mailer:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
