# 投資自動化プロジェクト

> Python + YAML/JSON ベースの投資ポートフォリオ管理・自動化ツール

## 概要

このプロジェクトは、複数の投資先（投資信託、国内株、米国株など）を一元管理し、リアルタイムで状況を把握・予測・可視化するための自動化スクリプトです。

### 目標
- 億り人（10億円資産保有者）になるための投資自動化ツール
- 現在の投資先の状況や危険信号をユーザに発信
- ニューストピックからおすすめの内容を共有

### 特徴

- **YAML/JSON管理**: 投資ポートフォリオをYAMLまたはJSONで定義
- **多言語対応**: 日本語フルサポート
- **自動集計**: カテゴリ別、資産別の自動集計
- **可視化**: matplotlib による多様なグラフ生成
- **GitHub Actions 対応**: Secrets に設定可能な構造

## 構成

```
fx_proj/
├── config/
│   └── portfolio.yaml          # 投資ポートフォリオ設定
├── src/
│   ├── portfolio_manager.py    # ポートフォリオ管理エンジン
│   └── visualizer.py           # 可視化エンジン
├── data/
│   ├── portfolio_status.json   # 出力: ポートフォリオステータス（JSON）
│   ├── portfolio_pie.png       # 出力: カテゴリ別円グラフ
│   ├── portfolio_bar.png       # 出力: 資産別棒グラフ
│   ├── portfolio_performance.png # 出力: パフォーマンスグラフ
│   └── portfolio_summary.png   # 出力: サマリーグラフ
├── run.py                      # メインスクリプト
├── requirements.txt            # 依存パッケージ
└── readme.md                   # このファイル
```

## インストール

### 1. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 2. ポートフォリオを設定

[config/portfolio.yaml](config/portfolio.yaml) を編集して、投資先を追加します。

## 新しい設定方針

`portfolio.yaml` は「静的マスタ」を中心に持つ構成へ変更しました。

- `holdings`: 現在の保有資産
- `watchlist`: 買い予定・監視対象
- `targets`: 目標配分

`manual_book_value` は累計の投資元本、`manual_current_value` は現在の評価額スナップショットです。
入金や買い増しのときだけ元本を更新し、普段は評価額だけが変わる想定です。
将来的には `quantity`, `average_cost`, `current_price`, `fx_rate` を埋めることで、自動価格取得へ移行しやすい形です。

自動取得に寄せるときは、最終的に `config` に残したい手入力は次のものです。

- `ticker`: APIで価格取得するための銘柄コード
- `quantity`: 保有株数 / 保有口数
- `average_cost`: 平均取得単価
- `currency`: 価格通貨
- `category`: 分析用カテゴリ
- `current_price`: 現在価格
- `fx_rate`: 現在価格の円換算用レート
- `cost_fx_rate`: 取得原価の円換算用レート
- `unit_base`: 投信など1万口単位の商品で使う基準値

理想形では、`manual_current_value` は不要になります。

```yaml
portfolio:
  holdings:
    - id: "nvidia"
      name: "NVIDIA"
      ticker: "NVDA"
      market: "US"
      asset_type: "stock"
      category: "ai_semiconductor"
      currency: "USD"
      price_source: "yfinance"
      quantity: 3
      average_cost: 126.50
      fx_rate: 145.0

  watchlist:
    - id: "rocket_lab"
      name: "ロケット・ラボ"
      ticker: "RKLB"
      market: "US"
      asset_type: "stock"
      category: "space"
      currency: "USD"
      price_source: "yfinance"
      planned_quantity: 5
```

## 使用方法

### 基本的な実行

```bash
# 価格スナップショットを取得
python run.py --action fetch

# サマリーを表示
python run.py --action summary

# 異常検知シグナルを表示
python run.py --action signals

# JSONファイルにエクスポート
python run.py --action json

# グラフを生成
python run.py --action viz

# すべてを実行
python run.py --action all
```

`fetch` は `price_source: yfinance` の銘柄だけを対象にして、
`data/price_snapshot.json` へ `current_price` と `fx_rate` を保存します。
`summary` / `json` / `all` は、このスナップショットが存在すればそちらを優先して評価額を計算します。

機微な保有数量や取得単価は `config/portfolio.private.yaml` に分離できます。
公開してもよい銘柄情報は `config/portfolio.yaml` に残し、`.gitignore` で private ファイルを除外します。

`signals` は、保有商品の価格スナップショットから次のような異常を判定します。

- 日次急変
- ATR基準の異常変動
- 出来高急増
- 価格上昇 + 出来高急増
- 50日移動平均割れ
- 200日移動平均割れ
- RSIの過熱 / 売られ過ぎ
- 同カテゴリ銘柄の同時急変

しきい値は `config/portfolio.yaml` の `monitoring` で管理します。

- `monitoring.defaults`: 全体のデフォルト
- `monitoring.categories.<category>`: カテゴリ単位の上書き
- `monitoring.assets.<asset_id>`: 個別銘柄の上書き

優先順位は `defaults < categories < assets` です。

### カスタム設定での実行

```bash
# 別の設定ファイルを使用
python run.py --config config/portfolio.local.yaml --action all

# 別の出力ディレクトリを指定
python run.py --output data/custom/ --action all
```

## 出力例

### サマリー出力
```
================================================================================
📊 投資ポートフォリオ サマリー
================================================================================

💰 総資産
  投資元本:        ¥5,224,283
  現在価値:        ¥7,426,247
  損益:            ¥2,201,964 (+42.15%)
  現金:            ¥6,500,000
  合計:            ¥13,926,247
  目標:            ¥100,000,000
  目標達成度:      13.93%
  ...
```

### グラフ出力
- **portfolio_summary.png**: 総資産内訳、損益、目標達成度などの4分割サマリー
- **portfolio_pie.png**: カテゴリ別の円グラフ
- **portfolio_bar.png**: 上位10資産の棒グラフ
- **portfolio_performance.png**: パフォーマンス（変動率）グラフ

## 今後の方針

このプロジェクトは「未来を当てる予測AI」ではなく、
「投資判断を支える意思決定補助システム」として育てていく方針が現実的です。

特に重視するのは次の4点です。

- 感情を排除して毎日同じ基準で状況を見る
- データを自動収集して手作業を減らす
- 異常値や急変を早く検知する
- テーマ偏りやリスク集中を可視化する

### 推奨ロードマップ

#### Phase 1: データ収集の自動化

- `yfinance` で保有銘柄の価格を更新
- `USDJPY=X`, `^VIX`, `^SOX`, `^GSPC` などの指標も取得
- `data/price_snapshot.json` に価格スナップショットを保存

#### Phase 2: 分析の拡張

- セクター比率
- 日次変動額
- 直近高値からの下落率
- 移動平均乖離
- 簡易ドローダウン
- 半導体・宇宙・防衛テーマの集中度

#### Phase 3: シグナル生成

まずはルールベースを優先します。

- 200日移動平均割れで警戒
- VIX急騰で買い場監視
- RSI低下で監視強化
- セクター比率が閾値超過で集中警告
- 1日変動が一定以上で異常通知

#### Phase 4: 通知と運用

- GitHub Actions で毎朝自動実行
- Discord / LINE / Slack 通知
- OpenAI API でニュース要約
- 決算日や関連ニュースの抽出

#### Phase 5: 機械学習

機械学習は最後で十分です。

- まずは特徴量設計とデータ品質の整備
- その後に `XGBoost` や `LightGBM` を検討
- 予測値そのものより、異常検知や状態分類に使う

## GitHub Actions での自動実行

### 構成

- `config/portfolio.yaml`
  公開してよい銘柄メタ情報
- `config/portfolio.private.yaml`
  保有数量・取得単価・原価為替などの非公開情報
- GitHub Secret `PORTFOLIO_PRIVATE_YAML`
  `portfolio.private.yaml` の内容を保存
- GitHub Secrets `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD`, `GMAIL_TO`
  Gmail 通知用

### Secret の登録方法

GitHub の `Settings -> Secrets and variables -> Actions -> New repository secret` から、
`PORTFOLIO_PRIVATE_YAML` という名前で登録します。

中身は `config/portfolio.private.yaml` の内容をそのまま貼り付ければ大丈夫です。

例:

```yaml
portfolio:
  holdings:
    - id: "nvidia"
      quantity: 4
      average_cost: 197.0175
      cost_fx_rate: 158.541123

    - id: "rocket_lab"
      quantity: 5
      average_cost: 80.1520
      cost_fx_rate: 157.910504
```

Gmail 通知を使う場合は、次の Secret も登録します。

- `GMAIL_SMTP_USER`
  送信元 Gmail アドレス
- `GMAIL_SMTP_APP_PASSWORD`
  Google アカウントのアプリ パスワード
- `GMAIL_TO`
  送信先メールアドレス

`GMAIL_SMTP_APP_PASSWORD` には通常のログインパスワードではなく、
Google アカウントで 2 段階認証を有効化したうえで発行した「アプリ パスワード」を入れてください。

### ワークフロー

このリポジトリには `.github/workflows/portfolio.yml` を同梱しています。
実行時に Secret から `config/portfolio.private.yaml` を復元し、価格取得と集計を行います。
生成された JSON や画像は GitHub Actions 上で artifact として保存しない構成にしているため、
結果がそのまま外部公開されにくい運用です。

```yaml
name: Portfolio Automation

on:
  workflow_dispatch:
  schedule:
    - cron: "0 * * * *"

jobs:
  portfolio-report:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Restore private portfolio config
        run: |
          mkdir -p config
          printf "%s" "${{ secrets.PORTFOLIO_PRIVATE_YAML }}" > config/portfolio.private.yaml

      - name: Fetch latest prices
        run: python run.py --action fetch

      - name: Generate report and signals
        run: python run.py --action all

      - name: Determine email mode
        id: email_mode
        run: |
          JST_HOUR=$(TZ=Asia/Tokyo date +%H)
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "mode=daily_digest" >> "$GITHUB_OUTPUT"
          elif [ "$JST_HOUR" = "08" ]; then
            echo "mode=daily_digest" >> "$GITHUB_OUTPUT"
          else
            echo "mode=high_only" >> "$GITHUB_OUTPUT"
          fi

      - name: Send Gmail report
        if: ${{ secrets.GMAIL_SMTP_USER != '' && secrets.GMAIL_SMTP_APP_PASSWORD != '' && secrets.GMAIL_TO != '' }}
        env:
          GMAIL_SMTP_USER: ${{ secrets.GMAIL_SMTP_USER }}
          GMAIL_SMTP_APP_PASSWORD: ${{ secrets.GMAIL_SMTP_APP_PASSWORD }}
          GMAIL_TO: ${{ secrets.GMAIL_TO }}
        run: python run.py --action email --email-mode ${{ steps.email_mode.outputs.mode }}
```

### セキュリティ方針

- `config/portfolio.private.yaml` は Git 管理しない
- `PORTFOLIO_PRIVATE_YAML` は GitHub Secret に保存する
- `data/*.json`, `data/*.png` は `.gitignore` 済み
- GitHub Actions では artifact upload を行わず、結果ファイルを外部保存しない
- Gmail 通知では数量や取得単価を本文に含めない

### 通知ルール

- 毎時 `00分` に workflow を実行
- `high` シグナルがある時だけ Gmail でアラート通知
- 毎朝 `08:00 JST` はシグナル有無に関係なく日報を送信
- `workflow_dispatch` の手動実行も日報モードで送信

通知先を追加する場合は、Discord Webhook などへ要約だけ送る形がおすすめです。
その場合も、数量や取得単価そのものは通知本文に含めない方が安全です。

## カスタマイズ

### ポートフォリオ設定（portfolio.yaml）

#### 資産を追加

```yaml
portfolio:
  holdings:
    - id: "new_stock"
      name: "新しい株式"
      ticker: "AAPL"
      market: "US"
      asset_type: "stock"
      category: "ai_semiconductor"
      currency: "USD"
      price_source: "yfinance"
```

数量や取得単価は `config/portfolio.private.yaml` 側に書きます。

#### カテゴリを追加

```yaml
targets:
  new_category:
    name: "カテゴリ名"
    target_ratio: 0.10      # 目標配分（10%）
    description: "説明"
```

### Python スクリプトでプログラマティックに使用

```python
from src.portfolio_manager import PortfolioManager
from src.visualizer import PortfolioVisualizer

# ポートフォリオを取得
manager = PortfolioManager("config/portfolio.yaml")

# サマリーを取得
summary = manager.get_portfolio_summary()
print(f"現在価値: ¥{summary['total_value']:,.0f}")

# カテゴリ別データを取得
categories = manager.get_category_summary()

# JSONにエクスポート
manager.export_json("data/portfolio_status.json")

# 可視化
visualizer = PortfolioVisualizer("data/portfolio_status.json")
visualizer.generate_all_plots()
```

## 今後の拡張予定

- [ ] リアルタイム株価取得（yfinance、API連携）
- [ ] 機械学習による利益予測
- [ ] メール/Slack 通知機能
- [ ] Webダッシュボード（Flask/Django）
- [ ] ポートフォリオ最適化提案
- [ ] 税効率の分析

## ライセンス

MIT License

## 注意事項

- このツールは参考情報を提供するもので、投資助言ではありません
- 投資判断はご自身の責任で行ってください
- 定期的にポートフォリオを見直してください
