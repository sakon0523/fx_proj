"""
yfinance を使った価格スナップショット取得
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml


class PriceFetcher:
    """価格スナップショット取得クラス"""

    def __init__(
        self,
        config_path: str = "config/portfolio.yaml",
        private_config_path: str | None = "config/portfolio.private.yaml",
    ):
        self.config_path = Path(config_path)
        self.private_config_path = (
            Path(private_config_path) if private_config_path is not None else None
        )
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)

        if self.private_config_path is not None and self.private_config_path.exists():
            with self.private_config_path.open("r", encoding="utf-8") as file:
                private_config = yaml.safe_load(file)
            config = self._merge_private_config(config, private_config)

        return config

    def _merge_private_config(self, config: dict, private_config: dict) -> dict:
        merged = dict(config)
        public_portfolio = dict(config.get("portfolio", {}))
        private_portfolio = private_config.get("portfolio", {})

        public_holdings = public_portfolio.get("holdings", [])
        private_holdings = {
            item["id"]: item for item in private_portfolio.get("holdings", []) if "id" in item
        }

        merged_holdings = []
        for item in public_holdings:
            private_item = private_holdings.get(item["id"], {})
            merged_item = dict(item)
            merged_item.update(private_item)
            merged_holdings.append(merged_item)

        public_portfolio["holdings"] = merged_holdings
        merged["portfolio"] = public_portfolio
        return merged

    def _iter_price_targets(self) -> List[dict]:
        portfolio = self.config.get("portfolio", {})
        holdings = portfolio.get("holdings", [])
        return [
            item
            for item in holdings
            if item.get("price_source") == "yfinance" and item.get("ticker")
        ]

    def _download_market_data(self, tickers: List[str], period: str = "1y"):
        import yfinance as yf

        if not tickers:
            return None

        return yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            progress=False,
            group_by="ticker",
            auto_adjust=False,
            threads=True,
        )

    def _extract_field_frame(self, data, field: str):
        if data is None or getattr(data, "empty", True):
            return None

        if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
            if field in data.columns.get_level_values(-1):
                return data.xs(field, axis=1, level=-1)
            return None

        if field in data.columns:
            return data[[field]]

        return None

    def _series_for_ticker(self, frame, ticker: str):
        if frame is None or getattr(frame, "empty", True):
            return None

        if ticker in frame:
            return frame[ticker].dropna()

        if frame.shape[1] == 1:
            return frame.iloc[:, 0].dropna()

        return None

    def _compute_rsi(self, close_series, period: int = 14) -> float | None:
        if close_series is None or len(close_series) < period + 1:
            return None

        delta = close_series.diff().dropna()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        avg_gain = gains.rolling(period).mean()
        avg_loss = losses.rolling(period).mean()

        last_avg_gain = avg_gain.iloc[-1]
        last_avg_loss = avg_loss.iloc[-1]
        if last_avg_loss == 0:
            return 100.0

        rs = last_avg_gain / last_avg_loss
        return float(100 - (100 / (1 + rs)))

    def _build_ticker_metrics(self, data, ticker: str) -> dict:
        close_frame = self._extract_field_frame(data, "Close")
        high_frame = self._extract_field_frame(data, "High")
        low_frame = self._extract_field_frame(data, "Low")
        volume_frame = self._extract_field_frame(data, "Volume")

        close_series = self._series_for_ticker(close_frame, ticker)
        high_series = self._series_for_ticker(high_frame, ticker)
        low_series = self._series_for_ticker(low_frame, ticker)
        volume_series = self._series_for_ticker(volume_frame, ticker)
        if close_series is None or close_series.empty:
            return {}

        metrics = {
            "current_price": float(close_series.iloc[-1]),
        }

        if len(close_series) >= 2:
            prev_close = float(close_series.iloc[-2])
            metrics["prev_close"] = prev_close
            if prev_close != 0:
                metrics["daily_change_pct"] = (
                    (metrics["current_price"] - prev_close) / prev_close
                ) * 100

        if len(close_series) >= 20:
            metrics["sma_20"] = float(close_series.tail(20).mean())
        if len(close_series) >= 50:
            metrics["sma_50"] = float(close_series.tail(50).mean())
        if len(close_series) >= 200:
            metrics["sma_200"] = float(close_series.tail(200).mean())

        if (
            high_series is not None
            and low_series is not None
            and len(close_series) >= 15
            and len(high_series) >= 15
            and len(low_series) >= 15
        ):
            prev_close_series = close_series.shift(1)
            true_range = (
                (high_series - low_series)
                .to_frame("hl")
                .join((high_series - prev_close_series).abs().to_frame("hc"))
                .join((low_series - prev_close_series).abs().to_frame("lc"))
                .max(axis=1)
                .dropna()
            )
            if len(true_range) >= 14:
                atr_14 = float(true_range.tail(14).mean())
                metrics["atr_14"] = atr_14
                if metrics["current_price"] != 0:
                    metrics["atr_14_pct"] = (atr_14 / metrics["current_price"]) * 100

        rsi_14 = self._compute_rsi(close_series, period=14)
        if rsi_14 is not None:
            metrics["rsi_14"] = rsi_14

        if volume_series is not None and not volume_series.empty:
            metrics["latest_volume"] = float(volume_series.iloc[-1])
            if len(volume_series) >= 20:
                avg_volume_20 = float(volume_series.tail(20).mean())
                metrics["avg_volume_20"] = avg_volume_20
                if avg_volume_20 > 0:
                    metrics["volume_ratio"] = metrics["latest_volume"] / avg_volume_20

        return metrics

    def build_snapshot(self) -> dict:
        targets = self._iter_price_targets()
        tickers = [item["ticker"] for item in targets]
        market_data = self._download_market_data(tickers, period="1y")
        fx_data = self._download_market_data(["USDJPY=X"], period="1mo")

        fx_rates: Dict[str, float] = {"JPY": 1.0}
        usd_jpy_metrics = self._build_ticker_metrics(fx_data, "USDJPY=X")
        if usd_jpy_metrics.get("current_price") is not None:
            fx_rates["USD"] = usd_jpy_metrics["current_price"]

        fetched_at = datetime.now(timezone.utc).isoformat()
        holdings: Dict[str, dict] = {}

        for item in targets:
            metrics = self._build_ticker_metrics(market_data, item["ticker"])
            if not metrics:
                continue

            snapshot_item = {
                "ticker": item["ticker"],
                "currency": item.get("currency", "JPY"),
                "price_source": item.get("price_source"),
                "fetched_at": fetched_at,
                **metrics,
            }

            currency = item.get("currency", "JPY")
            if currency != "JPY":
                fx_rate = fx_rates.get(currency)
                if fx_rate is not None:
                    snapshot_item["fx_rate"] = fx_rate

            holdings[item["id"]] = snapshot_item

        indicators = {
            "usd_jpy": {
                "ticker": "USDJPY=X",
                "fetched_at": fetched_at,
                **usd_jpy_metrics,
            }
            if usd_jpy_metrics
            else {}
        }

        return {
            "fetched_at": fetched_at,
            "fx_rates": fx_rates,
            "holdings": holdings,
            "indicators": indicators,
        }

    def save_snapshot(self, output_path: str = "data/price_snapshot.json", verbose: bool = True) -> dict:
        snapshot = self.build_snapshot()
        if not snapshot["holdings"]:
            raise RuntimeError(
                "価格を取得できませんでした。ネットワーク接続または yfinance の応答を確認してください。"
            )

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", encoding="utf-8") as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)

        if verbose:
            print(f"\n価格スナップショットを保存: {output_path}")
        return snapshot


if __name__ == "__main__":
    fetcher = PriceFetcher("config/portfolio.yaml")
    fetcher.save_snapshot()
