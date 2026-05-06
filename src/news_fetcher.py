"""
yfinance を使ったニュース取得
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml


class NewsFetcher:
    """保有銘柄のニュース取得クラス"""

    def __init__(
        self,
        config_path: str = "config/portfolio.yaml",
        private_config_path: str | None = "config/portfolio.private.yaml",
        max_articles_per_asset: int = 5,
    ):
        self.config_path = Path(config_path)
        self.private_config_path = (
            Path(private_config_path) if private_config_path is not None else None
        )
        self.max_articles_per_asset = max_articles_per_asset
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
            item["id"]: item
            for item in private_portfolio.get("holdings", [])
            if "id" in item
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

    def _iter_news_targets(self) -> List[dict]:
        portfolio = self.config.get("portfolio", {})
        holdings = portfolio.get("holdings", [])
        return [
            item
            for item in holdings
            if item.get("price_source") == "yfinance" and item.get("ticker")
        ]

    def _normalize_timestamp(self, timestamp: int | None) -> str | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    def _normalize_article(self, article: dict) -> dict | None:
        if not isinstance(article, dict):
            return None
        content = article.get("content", {})

        provider = content.get("provider", {}) or {}
        click_url = content.get("clickThroughUrl", {}) or {}
        canonical_url = content.get("canonicalUrl", {}) or {}

        return {
            "title": content.get("title"),
            "publisher": provider.get("displayName"),
            "link": click_url.get("url") or canonical_url.get("url"),
            "published_at": content.get("pubDate"),
            "summary": content.get("summary"),
        }

    def _fetch_articles_for_ticker(self, ticker: str) -> List[dict]:
        import yfinance as yf

        ticker_obj = yf.Ticker(ticker)
        raw_news = ticker_obj.news or []
        articles: List[dict] = []
        seen: set[str] = set()

        for raw_article in raw_news:
            article = self._normalize_article(raw_article)
            if article is None:
                continue

            unique_key = article["link"]
            if unique_key in seen:
                continue
            seen.add(unique_key)
            articles.append(article)

            if len(articles) >= self.max_articles_per_asset:
                break

        return articles

    def build_snapshot(self) -> dict:
        targets = self._iter_news_targets()
        generated_at = datetime.now(timezone.utc).isoformat()
        assets: Dict[str, dict] = {}
        total_articles = 0

        for item in targets:
            articles = self._fetch_articles_for_ticker(item["ticker"])
            assets[item["id"]] = {
                "asset_name": item["name"],
                "ticker": item["ticker"],
                "market": item.get("market"),
                "category": item.get("category"),
                "articles": articles,
            }
            total_articles += len(articles)

        return {
            "generated_at": generated_at,
            "summary": {
                "asset_count": len(assets),
                "article_count": total_articles,
            },
            "assets": assets,
        }

    def save_snapshot(
        self,
        output_path: str = "data/news_snapshot.json",
        verbose: bool = True,
    ) -> dict:
        snapshot = self.build_snapshot()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", encoding="utf-8") as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)

        if verbose:
            print(f"\nニューススナップショットを保存: {output_path}")
        return snapshot


if __name__ == "__main__":
    NewsFetcher().save_snapshot()
