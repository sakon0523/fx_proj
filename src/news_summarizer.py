"""
Gemini API を使ったニュース要約
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


class NewsSummarizer:
    """ニュース要約クラス"""

    def __init__(
        self,
        news_snapshot_path: str = "data/news_snapshot.json",
        model: str | None = None,
        api_key: str | None = None,
        max_articles_per_asset: int = 5,
    ):
        self.news_snapshot_path = Path(news_snapshot_path)
        env_model = os.environ.get("GEMINI_NEWS_MODEL")
        self.model = model or env_model or "gemini-2.5-flash-lite"
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.max_articles_per_asset = max_articles_per_asset

    def _load_snapshot(self) -> dict:
        if not self.news_snapshot_path.exists():
            raise FileNotFoundError(
                f"News snapshot file not found: {self.news_snapshot_path}"
            )

        with self.news_snapshot_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _get_client(self):
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY が設定されていません。")

        import google.genai as genai

        return genai.Client(api_key=self.api_key)

    def _build_prompt(self, asset_name: str, ticker: str, articles: List[dict]) -> str:
        article_lines = []
        for index, article in enumerate(
            articles[: self.max_articles_per_asset], start=1
        ):
            article_lines.append(
                "\n".join(
                    [
                        f"[{index}] title: {article.get('title', '')}",
                        f"publisher: {article.get('publisher', '')}",
                        f"published_at: {article.get('published_at', '')}",
                        f"summary: {article.get('summary', '')}",
                        f"link: {article.get('link', '')}",
                    ]
                )
            )

        articles_text = "\n\n".join(article_lines)

        return f"""
あなたは個人投資家向けのニュースアナリストです。
対象銘柄: {asset_name} ({ticker})

以下のニュースを読んで、日本語で要約してください。
返答は JSON のみで、次のキーを必ず含めてください。

{{
  "sentiment": "positive | neutral | negative",
  "impact": "low | medium | high",
  "summary": ["要点1", "要点2", "要点3"],
  "watch_points": ["注目点1", "注目点2"]
}}

条件:
- summary は 2〜3 項目
- watch_points は 0〜2 項目
- 相場影響が不明なら neutral / low を選ぶ
- JSON 以外の文章は出さない

ニュース:
{articles_text}
""".strip()

    def _build_batch_prompt(self, assets: Dict[str, dict]) -> str:
        asset_sections = []
        for asset_id, asset_data in assets.items():
            asset_name = asset_data.get("asset_name", asset_id)
            ticker = asset_data.get("ticker", "")
            article_lines = []
            for index, article in enumerate(
                asset_data.get("articles", [])[: self.max_articles_per_asset], start=1
            ):
                article_lines.append(
                    "\n".join(
                        [
                            f"[{index}] title: {article.get('title', '')}",
                            f"publisher: {article.get('publisher', '')}",
                            f"published_at: {article.get('published_at', '')}",
                            f"summary: {article.get('summary', '')}",
                            f"link: {article.get('link', '')}",
                        ]
                    )
                )
            articles_text = "\n\n".join(article_lines)
            asset_sections.append(
                "\n".join(
                    [
                        f"asset_id: {asset_id}",
                        f"asset_name: {asset_name}",
                        f"ticker: {ticker}",
                        "ニュース:",
                        articles_text,
                    ]
                )
            )

        all_assets_text = "\n\n".join(asset_sections)

        return f"""
あなたは個人投資家向けのニュースアナリストです。
以下の銘柄ごとのニュースを読んで、日本語で要約してください。
返答は JSON のみで、次のキーを必ず含めてください。

{{
  "assets": {{
    "<asset_id>": {{
      "sentiment": "positive | neutral | negative",
      "impact": "low | medium | high",
      "summary": ["要点1", "要点2", "要点3"],
      "watch_points": ["注目点1", "注目点2", "注目点3"],
      "headlines": ["見出し1", "見出し2", "見出し3"]
    }}
  }}
}}

条件:
- summary, watch_points, headlines はそれぞれ日本語で3項目ずつ記載してください
- headlinesの文言が英語の場合は、可能な限り日本語に翻訳してください
- 相場影響が不明なら neutral / low を選ぶ
- JSON 以外の文章は出さない
- 各 asset_id のキーはそのままにする

ニュース:
{all_assets_text}
""".strip()

    def _summarize_asset(self, client, asset_id: str, asset_data: dict) -> dict | None:
        articles = asset_data.get("articles", [])
        if not articles:
            return None

        prompt = self._build_prompt(
            asset_name=asset_data.get("asset_name", asset_id),
            ticker=asset_data.get("ticker", ""),
            articles=articles,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        content = self._clean_json_text(response.text)
        parsed = json.loads(content)
        parsed["asset_name"] = asset_data.get("asset_name", asset_id)
        parsed["ticker"] = asset_data.get("ticker", "")
        parsed["article_count"] = len(articles[: self.max_articles_per_asset])
        parsed["headlines"] = [article.get("title", "") for article in articles[:3]]
        return parsed

    def _clean_json_text(self, text: str) -> str:
        content = text.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return content

    def generate_summary(self) -> dict:
        snapshot = self._load_snapshot()
        client = self._get_client()

        assets_to_summarize = {
            asset_id: asset_data
            for asset_id, asset_data in snapshot.get("assets", {}).items()
            if asset_data.get("articles")
        }

        assets_summary: Dict[str, dict] = {}
        articles_used = 0

        if assets_to_summarize:
            prompt = self._build_batch_prompt(assets_to_summarize)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )

            content = self._clean_json_text(response.text)
            parsed = json.loads(content)
            parsed_assets = (
                parsed.get("assets", parsed) if isinstance(parsed, dict) else {}
            )

            for asset_id, asset_data in assets_to_summarize.items():
                asset_summary = parsed_assets.get(asset_id, {})
                articles = asset_data.get("articles", [])[: self.max_articles_per_asset]
                asset_summary["asset_name"] = asset_data.get("asset_name", asset_id)
                asset_summary["ticker"] = asset_data.get("ticker", "")
                asset_summary["article_count"] = len(articles)
                asset_summary["headlines"] = [
                    article.get("title", "") for article in articles[:3]
                ]
                assets_summary[asset_id] = asset_summary
                articles_used += len(articles)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_generated_at": snapshot.get("generated_at"),
            "model": self.model,
            "summary": {
                "asset_count": len(assets_summary),
                "articles_used": articles_used,
            },
            "assets": assets_summary,
        }

    def save_summary(
        self,
        output_path: str = "data/news_summary.json",
        verbose: bool = True,
    ) -> dict:
        summary = self.generate_summary()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)

        if verbose:
            print(f"\nニュース要約を保存: {output_path}")
        return summary


if __name__ == "__main__":
    NewsSummarizer().save_summary()
