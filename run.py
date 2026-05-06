#!/usr/bin/env python3
"""
投資自動化スクリプト - メインエントリーポイント
"""

import sys
import argparse
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from portfolio_manager import PortfolioManager


def main():
    parser = argparse.ArgumentParser(description="投資ポートフォリオ管理スクリプト")
    parser.add_argument(
        "--config", default="config/portfolio.yaml", help="設定ファイルパス"
    )
    parser.add_argument(
        "--action",
        default="summary",
        choices=[
            "summary",
            "json",
            "viz",
            "fetch",
            "signals",
            "news-fetch",
            "news-summary",
            "news",
            "email",
            "all",
        ],
        help="実行するアクション",
    )
    parser.add_argument("--output", default="data/", help="出力ディレクトリ")
    parser.add_argument(
        "--price-snapshot",
        default="data/price_snapshot.json",
        help="価格スナップショットJSONの出力先/読込先",
    )
    parser.add_argument(
        "--news-snapshot",
        default="data/news_snapshot.json",
        help="ニューススナップショットJSONの出力先/読込先",
    )
    parser.add_argument(
        "--news-summary",
        default="data/news_summary.json",
        help="ニュース要約JSONの出力先/読込先",
    )
    parser.add_argument(
        "--email-mode",
        default="daily_digest",
        choices=["daily_digest", "high_only"],
        help="メール通知モード",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="標準出力を最小限にする",
    )
    parser.add_argument(
        "--enable-news-summary",
        default="true",
        help="ニュース要約処理を有効にするかどうか (true/false)",
    )

    args = parser.parse_args()
    args.enable_news_summary = str(args.enable_news_summary).lower() in (
        "1",
        "true",
        "yes",
    )

    if args.action in ["fetch", "all"]:
        try:
            from price_fetcher import PriceFetcher
        except ImportError as exc:
            raise SystemExit(
                "yfinance が必要です。`pip install -r requirements.txt` を実行してください。"
            ) from exc

        fetcher = PriceFetcher(args.config)
        try:
            fetcher.save_snapshot(args.price_snapshot, verbose=not args.quiet)
        except RuntimeError as exc:
            raise SystemExit(f"価格取得に失敗しました: {exc}") from exc

    if args.action in ["news-fetch", "news", "all"]:
        try:
            from news_fetcher import NewsFetcher
        except ImportError as exc:
            raise SystemExit(
                "ニュース取得には yfinance が必要です。`pip install -r requirements.txt` を実行してください。"
            ) from exc

        news_fetcher = NewsFetcher(args.config)
        news_fetcher.save_snapshot(args.news_snapshot, verbose=not args.quiet)

    if args.action in ["news-summary", "news"]:
        if not args.enable_news_summary:
            if not args.quiet:
                print("ニュース要約処理をスキップしました。")
        else:
            try:
                from news_summarizer import NewsSummarizer
            except ImportError as exc:
                raise SystemExit(
                    "ニュース要約には openai パッケージが必要です。`pip install -r requirements.txt` を実行してください。"
                ) from exc

            summarizer = NewsSummarizer(news_snapshot_path=args.news_snapshot)
            summarizer.save_summary(args.news_summary, verbose=not args.quiet)

    elif args.action == "all":
        try:
            from news_summarizer import NewsSummarizer
        except ImportError:
            summarizer = None
        else:
            if args.enable_news_summary and Path(args.news_snapshot).exists():
                try:
                    summarizer = NewsSummarizer(news_snapshot_path=args.news_snapshot)
                    summarizer.save_summary(args.news_summary, verbose=not args.quiet)
                except RuntimeError:
                    pass
            elif not args.quiet:
                print("ニュース要約処理をスキップしました。")

    manager = PortfolioManager(args.config, price_snapshot_path=args.price_snapshot)

    if args.action in ["summary", "all"]:
        if not args.quiet:
            print("✅ ポートフォリオマネージャを起動します\n")
            manager.print_summary()

    if args.action in ["signals", "all"]:
        from signal_engine import SignalEngine

        engine = SignalEngine(args.config, args.price_snapshot)
        if not args.quiet:
            engine.print_signals()
        signal_path = Path(args.output) / "signals.json"
        engine.export_json(str(signal_path), verbose=not args.quiet)

    if args.action in ["json", "all"]:
        json_path = Path(args.output) / "portfolio_status.json"
        manager.export_json(str(json_path), verbose=not args.quiet)

    if args.action == "email":
        from email_notifier import EmailNotifier

        notifier = EmailNotifier()
        portfolio_status_path = Path(args.output) / "portfolio_status.json"
        signals_path = Path(args.output) / "signals.json"
        notifier.send_report(
            str(portfolio_status_path),
            str(signals_path),
            mode=args.email_mode,
            news_summary_path=args.news_summary,
            verbose=not args.quiet,
        )

    if args.action in ["viz", "all"]:
        from visualizer import PortfolioVisualizer

        json_path = Path(args.output) / "portfolio_status.json"
        if json_path.exists():
            visualizer = PortfolioVisualizer(str(json_path))
            visualizer.generate_all_plots()
        else:
            print(
                "❌ JSON ファイルが見つかりません。先に --action json を実行してください。"
            )


if __name__ == "__main__":
    main()
