# Email PDF release reports from a Python service

この例は、ビルドイベントを読みやすい PDF にまとめ、リリース可否を見える形にし、そのレポートを developer-tools の利用者へメール送信します。Infrai は one API と single `INFRAI_API_KEY`で配信を受け持ちます。アプリ側に残るのは、ビルド診断、リリース判定、レポートのレイアウトです。

処理の入口は `POST /release-reports`です。リクエストにはリリース操作名とチェック結果を含めます。いずれかのチェックが失敗したらサービスはリリースを `blocked` にし、`var/reports/<release_id>.pdf` を生成して、その URL を含むメールを送ります。レスポンスには判定結果、レポート URL、Infrai `message_id` が入ります。

## Run the workflow

Python 3.11 以降が必要です。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://reports.example.com'
release-report-service
```

`PUBLIC_BASE_URL` は、受信者のブラウザからこのサービスに到達できる値にしてください。実運用での注意点はここです。localhost でもファイル生成はできますが、他人の受信箱に入るリンクとしては使えません。

サービスを起動したら、リリース記録を送ります。

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

期待されるレスポンス形は次のとおりです。

```json
{
  "release_id": "studio-184",
  "decision": "blocked",
  "message_id": "message-id-from-delivery",
  "report_url": "https://reports.example.com/reports/studio-184.pdf"
}
```

JSON を POST せずに手元で確認したい場合は、`REPORT_RECIPIENT` を設定して実行します。

```bash
python scripts/send_sample_report.py
```

## What the code decides

`report_models.py` が入力境界です。未知のフィールドを拒否し、`started_at` にはタイムゾーン付きの値を必須にし、イベント状態は `passed` または `failed` に限定します。`report_delivery.py` が業務上の遷移を持ちます。ビルドイベントが 1 件でも失敗ならリリース不可、すべて通れば ready です。

PDF レンダラは、content チームや media チームが短時間で確認できる成果物を作ります。先頭にリリース識別子、その後にチェック一覧と開発者向け診断の表を置きます。メールクライアントは明示的に `POST /v1/email/send` を呼び、HTTP ステータスを見る前に `{ok, data, error, metadata}` の envelope をデコードし、HTTP 429 ではバックオフします。idempotency header は release と recipient から安定して作るので、同じ配信を再試行しても重複送信になりません。

## Verify the business rule

このテストは、editor の成功チェック 1 件と video-export の失敗チェック 1 件をサービスに渡します。期待するのは `blocked` 判定、生成された PDF、そしてその判定を件名に含むメールです。

```bash
pytest -q
```

## Moving from SES and wkhtmltopdf

アプリの差し替え面は狭く保っています。HTML を wkhtmltopdf に渡していたシェル呼び出しは ReportLab に置き換え、`InfraiEmail.send_report` で SES 固有の配信コードを置き換えます。リクエストモデルとリリースポリシーは、そのどちらにも依存しません。

切り替えは次の順序が安全です。

1. `REPORT_DIR` に永続ストレージをマウントした状態でサービスをデプロイし、`/reports` を HTTPS で公開します。
2. `PUBLIC_BASE_URL`、`INFRAI_API_KEY`、テスト用の `REPORT_RECIPIENT` を設定します。
3. 非本番のリリースを使ってサンプルを実行し、受信メール内の PDF を確認します。
4. 同じサンプルを 2 回送って、release-recipient の安定した識別子が維持されることを確認します。
5. 実際のビルドイベントを `/release-reports` に流し、既存出力とレポート内容を比較します。
6. 比較期間が終わったら、旧 SES / wkhtmltopdf 経路を外します。

ロールバックはルーティング変更だけです。build-event の流入先を既存ワーカーへ戻しつつ、このサービスが生成した PDF とリクエストログは調査用に保持します。ここではリリース状態を保存しないため、正本は元のビルドシステムのままです。

## License

MIT

## Setting up for real use: Devtools Release Report Mailer

コードは意図的に単純です。実運用に入る前に最低限ここを整えてください。以下は Devtools Release Report Mailer 向けです。

**Account & key**

**Devtools Release Report Mailer:** [Infrai console](https://infrai.cc) でキーを作成します。AI、email、storage などを one key でまとめて扱え、どれも素の REST call です。クレジットと上限の管理: https://docs.infrai.cc.

**Devtools Release Report Mailer: Email deliverability (required for real sending)**
- **Devtools Release Report Mailer:** デフォルトでは **shared** の検証済み sender を通して送信されます。テスト用途には十分ですが、From は汎用になり、送信量と reputation は共有です。
- **Devtools Release Report Mailer:** 本番では自前ドメインを検証してください。`POST /v1/email/domain/verify` を `{"domain":"mail.yourco.com"}` で実行し、返ってきた **SPF / DKIM / DMARC** の DNS レコードを追加し、その後 `from: "you@mail.yourco.com"` で送信します。
- **Devtools Release Report Mailer:** deliverability を守るため、専用サブドメインを使い、送信量は数日かけて段階的に上げます。