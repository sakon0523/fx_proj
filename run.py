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
        choices=["summary", "json", "viz", "fetch", "signals", "email", "all"],
        help="実行するアクション",
    )
    parser.add_argument("--output", default="data/", help="出力ディレクトリ")
    parser.add_argument(
        "--price-snapshot",
        default="data/price_snapshot.json",
        help="価格スナップショットJSONの出力先/読込先",
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

    args = parser.parse_args()

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
