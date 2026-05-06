"""
Gmail SMTP を使った日次レポート通知
"""

from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


class EmailNotifier:
    """メール通知クラス"""

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        to_address: str | None = None,
        from_address: str | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.environ.get("GMAIL_SMTP_USER")
        self.smtp_password = smtp_password or os.environ.get("GMAIL_SMTP_APP_PASSWORD")
        self.to_address = to_address or os.environ.get("GMAIL_TO")
        self.from_address = from_address or os.environ.get(
            "GMAIL_FROM", self.smtp_user or ""
        )

    def _load_json(self, path: str) -> dict:
        file_path = Path(path)
        if not file_path.exists():
            return {}

        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _build_subject(self, summary: dict, signals: dict, mode: str) -> str:
        total_value = summary.get("total_value", 0)
        total_change = summary.get("total_change", 0)
        signal_total = signals.get("summary", {}).get("total", 0)
        high_total = signals.get("summary", {}).get("high", 0)
        prefix = "[Portfolio Alert]" if mode == "high_only" else "[Portfolio Daily]"
        return (
            f"{prefix} 現在価値 ¥{total_value:,.0f} / 損益 {total_change:+,.0f} "
            f"/ high {high_total} / signals {signal_total}"
        )

    def _build_news_section(self, news_summary: dict, mode: str) -> str:
        assets = news_summary.get("assets", {})
        if not assets or mode == "high_only":
            return ""

        lines = ["", "ニュース要約"]
        for asset in assets.values():
            summary_lines = asset.get("summary", [])
            watch_points = asset.get("watch_points", [])
            lines.append(
                f"- {asset.get('asset_name', '')} ({asset.get('ticker', '')}) "
                f"[{asset.get('sentiment', 'neutral')}/{asset.get('impact', 'low')}]"
            )
            for point in summary_lines[:3]:
                lines.append(f"  - {point}")
            for point in watch_points[:2]:
                lines.append(f"  - 注目: {point}")

        return "\n".join(lines)

    def _build_body(self, summary: dict, signals: dict, news_summary: dict, mode: str) -> str:
        all_signal_items = signals.get("signals", [])
        if mode == "high_only":
            signal_items = [
                item for item in all_signal_items if item.get("severity") == "high"
            ]
            title = "高優先度アラート"
        else:
            signal_items = all_signal_items
            title = "投資日報"

        signal_lines = (
            "\n".join(f"- [{item['severity']}] {item['message']}" for item in signal_items[:10])
            if signal_items
            else "- 異常シグナルはありません"
        )

        news_section = self._build_news_section(news_summary, mode)

        return f"""{title}

保有状況
- 現在価値: ¥{summary.get("total_value", 0):,.0f}
- 投資元本: ¥{summary.get("total_invested", 0):,.0f}
- 損益: ¥{summary.get("total_change", 0):+,.0f}
- 損益率: {summary.get("overall_change_rate", 0):+.2f}%
- 保有銘柄数: {summary.get("active_assets_count", 0)}

シグナル概要
- total: {signals.get("summary", {}).get("total", 0)}
- high: {signals.get("summary", {}).get("high", 0)}
- medium: {signals.get("summary", {}).get("medium", 0)}
- low: {signals.get("summary", {}).get("low", 0)}

シグナル詳細
{signal_lines}
{news_section}
"""

    def send_report(
        self,
        portfolio_status_path: str = "data/portfolio_status.json",
        signals_path: str = "data/signals.json",
        news_summary_path: str = "data/news_summary.json",
        mode: str = "daily_digest",
        verbose: bool = True,
    ) -> bool:
        if not self.smtp_user or not self.smtp_password or not self.to_address:
            raise RuntimeError(
                "Gmail 送信に必要な環境変数が不足しています。"
                " GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD / GMAIL_TO を設定してください。"
            )

        portfolio_status = self._load_json(portfolio_status_path)
        summary = portfolio_status.get("summary", {})
        signals = self._load_json(signals_path)
        news_summary = self._load_json(news_summary_path)
        high_total = signals.get("summary", {}).get("high", 0)

        if mode == "high_only" and high_total <= 0:
            if verbose:
                print("\nhigh シグナルがないため、メール送信をスキップしました。")
            return False

        message = EmailMessage()
        message["Subject"] = self._build_subject(summary, signals, mode)
        message["From"] = self.from_address
        message["To"] = self.to_address
        message.set_content(self._build_body(summary, signals, news_summary, mode))

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.smtp_user, self.smtp_password)
            smtp.send_message(message)

        if verbose:
            print(f"\nメールを送信: {self.to_address}")
        return True


if __name__ == "__main__":
    EmailNotifier().send_report()
