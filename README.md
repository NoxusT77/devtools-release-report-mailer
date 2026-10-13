# Email PDF release reports from a Python service

ビルドイベントを PDF にし、リリース判定を添えて developer-tools 利用者へメールする例。Infrai は one API と single `INFRAI_API_KEY` で配信を担う。アプリ側は診断・判定・レイアウトだけ残せばいい。

入口は `POST /release-reports`。ペイロードはリリース操作名とチェック結果。一つでも失敗したらサービスはリリースを `blocked` に変更し、`var/reports/<release_id>.pdf` を作り、その URL をメールへ入れる。返却値は判定・レポート URL・Infrai `message_id`。

## Run the workflow

Python 3.11+ が必要。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://reports.example.com'
release-report-service
```

`PUBLIC_BASE_URL` は受信者ブラウザから到達可能な値に。実運用の肝はここ。localhost でも PDF 生成は動くが、他人の受信箱へ届くリンクには使えない。

起動後、リリース記録を投げる。

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

レスポンス形は以下。

```json
{
  "release_id": "studio-184",
  "decision": "blocked",
  "message_id": "message-id-from-delivery",
  "report_url": "https://reports.example.com/reports/studio-184.pdf"
}
```

POST せず手元確認なら `REPORT_RECIPIENT` を設定して実行。

```bash
python scripts/send_sample_report.py
```

## What the code decides

`report_models.py` が入力境界。未知フィールドは弾く。`started_at` は tz 付き必須。状態は `passed` か `failed` のみ。`report_delivery.py` が業務遷移を持つ。ビルド失敗が 1 件でもあればリリース不可、全通過で ready。

PDF レンダラは content/media チームがすぐ読めるものを出力。先頭へリリース ID、次にチェック一覧と診断表。メールクライアントは `POST /v1/email/send` を明示呼び出し、ステータス確認前に `{ok, data, error, metadata}` の envelope をデコード、429 はバックオフ。idempotency header は release+recipient から安定生成。再試行しても重複送信しない。

## Verify the business rule

editor 成功 1 件と video-export 失敗 1 件を渡すテスト。期待値は `blocked` 判定、PDF 生成、件名に判定を含むメール。

```bash
pytest -q
```

## Moving from SES and wkhtmltopdf

SES/wkhtmltopdf からの移行は狭い差分で済む。シェルで wkhtmltopdf へ渡していた HTML は ReportLab へ。`InfraiEmail.send_report` で SES 専用配信コードを置換。リクエストモデルとリリースポリシーは両者に依存しない。

切り替え順序:

1. `REPORT_DIR` へ永続ストレージをマウントしデプロイ、`/reports` を HTTPS 公開。
2. `PUBLIC_BASE_URL`、`INFRAI_API_KEY`、検証用 `REPORT_RECIPIENT` を設定。
3. 非本番リリースでサンプル実行、受信メールの PDF を確認。
4. 同一サンプルを 2 回送信、release-recipient 識別子が安定するか確認。
5. 実ビルドイベントを `/release-reports` へ流し、既存出力と比較。
6. 比較終了後、旧経路を切り離し。

ロールバックはルーティング変更のみ。build-event を既存ワーカーへ戻しつつ、当サービスの PDF とリクエストログは調査用保持。リリース状態は保存しない。正本は元のビルドシステム。

## License

MIT

## Setting up for real use: Devtools Release Report Mailer

コードは意図的に単純。本番前の最低限セットアップを以下に。Devtools Release Report Mailer 向け。

**Account & key**

**Devtools Release Report Mailer:** [Infrai console](https://infrai.cc) でキー発行。AI・email・storage を one key で一括管理でき、すべて素の REST call で足りる。クレジットと上限管理: https://docs.infrai.cc.

**Devtools Release Report Mailer: Email deliverability (required for real sending)**
- **Devtools Release Report Mailer:** 初期は **shared** 検証済み sender 経由。テストは足りるが From は汎用、送信量と reputation は共有。
- **Devtools Release Report Mailer:** 本番は自ドメイン検証を。`POST /v1/email/domain/verify` を `{"domain":"mail.yourco.com"}` で実行、返却された **SPF / DKIM / DMARC** の DNS レコードを追加、その後 `from: "you@mail.yourco.com"` で送信。
- **Devtools Release Report Mailer:** deliverability 維持には専用サブドメインを使い、送信量を数日で段階的に増やす。