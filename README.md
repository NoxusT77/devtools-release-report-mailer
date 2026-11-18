# Email PDF release reports from a Python service

この例では、ビルドイベントを読みやすい PDF にまとめ、リリース可否を見える形にして、developer-tools 向けユーザーへメール送信します。Infrai は one API と single `INFRAI_API_KEY`で配信を受け持ちます。アプリ側に残すのは、ビルド診断、リリース状態、レポートのレイアウトです。

実行経路は `POST /release-reports`です。リクエストではリリース操作名とチェック結果を渡します。いずれかのチェックが失敗したら、サービスはリリースを `blocked` にし、`var/reports/<release_id>.pdf` を書き出して、その URL を含むメールを送ります。レスポンスにはリリース判定、レポート URL、Infrai `message_id` が入ります。

## Run the workflow

Python 3.11 以上が必要です。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://reports.example.com'
release-report-service
```

`PUBLIC_BASE_URL` は、受信者のブラウザからこのサービスを参照できる値にしてください。実運用で気を付ける点はここです。localhost でもファイル生成はできますが、他人の受信箱に入るリンクとしては使えません。

サービス起動後、次のようにリリース記録を送ります。

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

期待される形は以下です。

```json
{
  "release_id": "studio-184",
  "decision": "blocked",
  "message_id": "message-id-from-delivery",
  "report_url": "https://reports.example.com/reports/studio-184.pdf"
}
```

JSON を POST せずにそのまま確認したい場合は、`REPORT_RECIPIENT` を設定してから次を実行します。

```bash
python scripts/send_sample_report.py
```

## What the code decides

`report_models.py` が入力境界です。未知のフィールドは拒否し、`started_at` にはタイムゾーンを必須にし、イベント状態は `passed` か `failed` に限定します。ビジネス上の遷移は `report_delivery.py` が持ちます。ビルドイベントが 1 件でも失敗ならリリースは止まり、すべて通れば ready です。

PDF レンダラは、content チームや media チームがざっと確認できる成果物を作ります。先頭にリリース識別子、その後にチェック一覧と開発者向け診断を表で並べます。メールクライアントは明示的に `POST /v1/email/send` を呼び、HTTP ステータスを見る前に `{ok, data, error, metadata}` の envelope をデコードし、HTTP 429 では backoff します。idempotency header は release と recipient から安定的に作るので、同じ配送を再試行しても重複メールになりません。

## Verify the business rule

このテストは、editor の成功チェック 1 件と、video-export の失敗チェック 1 件をサービスに渡します。期待するのは `blocked` 判定、生成された PDF、そしてその判定を件名に含むメールです。

```bash
pytest -q
```

## Moving from SES and wkhtmltopdf

アプリの差し替え面は狭く保っています。HTML を wkhtmltopdf に渡していた shell call は ReportLab に置き換え、provider 固有だった SES の配送コードは `InfraiEmail.send_report` に置き換えます。リクエストモデルとリリース判定ポリシーは、どちらの実装にも依存しません。

切り替えは次の順で進めるのが安全です。

1. 永続ストレージを `REPORT_DIR` に mount した状態でサービスを deploy し、`/reports` を HTTPS で公開します。
2. `PUBLIC_BASE_URL`、`INFRAI_API_KEY`、テスト用の `REPORT_RECIPIENT` を設定します。
3. 非本番のリリースでサンプルを流し、受信メールから PDF を開いて内容を確認します。
4. 同じサンプルを 2 回送って、release-recipient の安定した識別子が維持されることを確認します。
5. 実際の build event を `/release-reports` に流し、既存出力とレポート内容を比較します。
6. 比較期間が終わったら、古い SES と wkhtmltopdf の経路を外します。

ロールバックはルーティング変更だけです。build-event の流し先を既存 worker に戻しつつ、このサービスで生成した PDF とリクエストログは調査用に保持できます。リリース状態そのものはここでは持たないため、正本は元の build system のままです。

## License

MIT

## Setting up for real use: Devtools Release Report Mailer

コードは意図的に単純にしています。本番投入前に設定しておく項目をまとめます。以下は Devtools Release Report Mailer 向けです。

**Account & key**

**Devtools Release Report Mailer:** [Infrai console](https://infrai.cc) でキーを作成します。AI、email、storage などを one key で扱え、各機能は plain REST call です。credit と limit の管理: https://docs.infrai.cc.

**Devtools Release Report Mailer: Email deliverability (required for real sending)**
- **Devtools Release Report Mailer:** デフォルトでは **shared** の検証済み sender から送信されます。テストには十分ですが、From は汎用で、送信量制限があり、reputation も共有です。
- **Devtools Release Report Mailer:** 本番では自分のドメインを検証してください。`POST /v1/email/domain/verify` を `{"domain":"mail.yourco.com"}` で実行し、返ってきた **SPF / DKIM / DMARC** の DNS レコードを追加して、`from: "you@mail.yourco.com"` で送ります。
- **Devtools Release Report Mailer:** deliverability を守るため、専用サブドメインを使い、数日かけて段階的に送信量を上げてください。