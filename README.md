# 投資ポートフォリオ自動化

保有銘柄の価格取得、集計、異常検知、メール通知を行う Python スクリプトです。

## 構成

- `config/portfolio.yaml`
  公開してよい銘柄情報と監視設定
- `config/portfolio.private.yaml`
  数量、取得単価、原価為替などの非公開情報
- `run.py`
  実行エントリーポイント
- `src/price_fetcher.py`
  `yfinance` から価格と指標を取得
- `src/portfolio_manager.py`
  ポートフォリオ集計
- `src/signal_engine.py`
  異常検知
- `src/email_notifier.py`
  Gmail 通知

## セットアップ

```bash
pip install -r requirements.txt
```

`config/portfolio.yaml` と `config/portfolio.private.yaml` はローカル管理前提です。  
必要に応じて GitHub Actions の Secret から復元します。

削除時の復旧用に `config/portfolio-sample.yaml` と `config/portfolio.private-sample.yaml` を置いています。

## 実行方法

```bash
# 価格取得
python run.py --action fetch

# サマリー表示
python run.py --action summary

# 異常検知
python run.py --action signals

# 集計・シグナル・JSON 出力
python run.py --action all

# メール送信
python run.py --action email --email-mode daily_digest
python run.py --action email --email-mode high_only
```

## 監視設定

`config/portfolio.yaml` の `monitoring` で管理します。

- `monitoring.defaults`
  全体のデフォルト
- `monitoring.categories.<category>`
  カテゴリ単位の上書き
- `monitoring.assets.<asset_id>`
  銘柄単位の上書き

優先順位は `defaults < categories < assets` です。

## GitHub Actions

`.github/workflows/portfolio.yml` で自動実行します。

- 毎時 `00分` に実行
- `08:00 JST` は日報メール送信
- それ以外は `high` シグナルがある時だけ通知
- `main` への push でも実行
- 手動実行 `workflow_dispatch` でも実行

## GitHub Secrets

必須:

- `PORTFOLIO_YAML`
  `config/portfolio.yaml` の中身をそのまま登録
- `PORTFOLIO_PRIVATE_YAML`
  `config/portfolio.private.yaml` の中身をそのまま登録

Gmail 通知を使う場合:

- `GMAIL_SMTP_USER`
  送信元 Gmail アドレス
- `GMAIL_SMTP_APP_PASSWORD`
  Google のアプリ パスワード
- `GMAIL_TO`
  送信先メールアドレス

`GMAIL_SMTP_APP_PASSWORD` には通常のログインパスワードではなく、Google アカウントで発行したアプリ パスワードを使います。

## セキュリティ

- `config/portfolio.yaml` は `.gitignore` 済み
- `config/portfolio.private.yaml` は `.gitignore` 済み
- `data/*.json`, `data/*.png`, `data/*.csv` は `.gitignore` 済み
- GitHub Actions では artifact を保存しない
- 通知本文には数量や取得単価を含めない

## 注意

- このツールは投資助言ではありません
- 投資判断はご自身の責任で行ってください
