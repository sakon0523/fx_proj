"""
投資ポートフォリオ管理スクリプト
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class Asset:
    """保有資産情報"""

    id: str
    name: str
    ticker: str
    market: str
    asset_type: str
    category: str
    currency: str
    book_value: float
    current_value: float
    source: str
    note: Optional[str] = None
    quantity: Optional[float] = None
    average_cost: Optional[float] = None
    current_price: Optional[float] = None
    fx_rate: Optional[float] = None
    cost_fx_rate: Optional[float] = None
    unit_base: float = 1.0

    @property
    def change(self) -> float:
        return self.current_value - self.book_value

    @property
    def change_rate(self) -> float:
        if self.book_value <= 0:
            return 0.0
        return (self.change / self.book_value) * 100


@dataclass
class WatchItem:
    """監視対象・買い候補"""

    id: str
    name: str
    ticker: str
    market: str
    asset_type: str
    category: str
    currency: str
    note: Optional[str] = None
    planned_budget: Optional[float] = None
    planned_quantity: Optional[float] = None


class PortfolioManager:
    """ポートフォリオ管理クラス"""

    def __init__(
        self,
        config_path: str = "config/portfolio.yaml",
        price_snapshot_path: Optional[str] = "data/price_snapshot.json",
        private_config_path: Optional[str] = "config/portfolio.private.yaml",
    ):
        self.config_path = Path(config_path)
        self.private_config_path = (
            Path(private_config_path) if private_config_path is not None else None
        )
        self.config = self._load_config()
        self.price_snapshot_path = (
            Path(price_snapshot_path) if price_snapshot_path is not None else None
        )
        self.price_snapshot = self._load_price_snapshot()
        self.assets = self._parse_assets()
        self.watchlist = self._parse_watchlist()

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

    def _portfolio_config(self) -> dict:
        return self.config.get("portfolio", {})

    def _load_price_snapshot(self) -> dict:
        if self.price_snapshot_path is None or not self.price_snapshot_path.exists():
            return {}

        with self.price_snapshot_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _get_snapshot_item(self, item_id: str) -> dict:
        holdings = self.price_snapshot.get("holdings", {})
        return holdings.get(item_id, {})

    def _apply_price_snapshot(self, item: dict) -> dict:
        snapshot_item = self._get_snapshot_item(item["id"])
        if not snapshot_item:
            return item

        merged = dict(item)
        if snapshot_item.get("current_price") is not None:
            merged["current_price"] = snapshot_item["current_price"]
        if snapshot_item.get("fx_rate") is not None:
            merged["fx_rate"] = snapshot_item["fx_rate"]
        if snapshot_item.get("fetched_at") is not None:
            merged["fetched_at"] = snapshot_item["fetched_at"]
        return merged

    def _compute_book_value(self, item: dict) -> float:
        if item.get("manual_book_value") is not None:
            return float(item["manual_book_value"])

        quantity = item.get("quantity")
        average_cost = item.get("average_cost")
        cost_fx_rate = item.get("cost_fx_rate", item.get("fx_rate", 1.0))
        unit_base = item.get("unit_base", 1.0)

        if quantity is not None and average_cost is not None:
            return (
                float(quantity) / float(unit_base) * float(average_cost) * float(cost_fx_rate)
            )

        raise ValueError(
            f"Asset '{item.get('name', 'unknown')}' is missing book value inputs."
        )

    def _compute_current_value(self, item: dict) -> tuple[float, str]:
        if item.get("manual_current_value") is not None:
            return float(item["manual_current_value"]), "manual_snapshot"

        quantity = item.get("quantity")
        current_price = item.get("current_price")
        fx_rate = item.get("fx_rate", 1.0)
        unit_base = item.get("unit_base", 1.0)

        if quantity is not None and current_price is not None:
            return (
                float(quantity) / float(unit_base) * float(current_price) * float(fx_rate),
                "price_formula",
            )

        raise ValueError(
            f"Asset '{item.get('name', 'unknown')}' is missing current value inputs. "
            "price_source が yfinance の場合は先に `python run.py --action fetch` を実行してください。"
        )

    def _parse_assets(self) -> List[Asset]:
        holdings = self._portfolio_config().get("holdings", [])
        assets: List[Asset] = []

        for raw_item in holdings:
            item = self._apply_price_snapshot(raw_item)
            current_value, source = self._compute_current_value(item)
            assets.append(
                Asset(
                    id=item["id"],
                    name=item["name"],
                    ticker=item["ticker"],
                    market=item["market"],
                    asset_type=item["asset_type"],
                    category=item["category"],
                    currency=item.get("currency", "JPY"),
                    book_value=self._compute_book_value(item),
                    current_value=current_value,
                    source="price_snapshot" if source == "price_formula" and item.get("fetched_at") else source,
                    note=item.get("note"),
                    quantity=item.get("quantity"),
                    average_cost=item.get("average_cost"),
                    current_price=item.get("current_price"),
                    fx_rate=item.get("fx_rate"),
                    cost_fx_rate=item.get("cost_fx_rate"),
                    unit_base=float(item.get("unit_base", 1.0)),
                )
            )

        return assets

    def _parse_watchlist(self) -> List[WatchItem]:
        items = self._portfolio_config().get("watchlist", [])
        return [
            WatchItem(
                id=item["id"],
                name=item["name"],
                ticker=item["ticker"],
                market=item["market"],
                asset_type=item["asset_type"],
                category=item["category"],
                currency=item.get("currency", "JPY"),
                note=item.get("note"),
                planned_budget=item.get("planned_budget"),
                planned_quantity=item.get("planned_quantity"),
            )
            for item in items
        ]

    def get_portfolio_summary(self) -> Dict:
        total_value = sum(asset.current_value for asset in self.assets)
        total_invested = sum(asset.book_value for asset in self.assets)
        total_change = total_value - total_invested
        overall_rate = (total_change / total_invested * 100) if total_invested > 0 else 0

        return {
            "total_value": total_value,
            "total_invested": total_invested,
            "total_change": total_change,
            "overall_change_rate": overall_rate,
            "active_assets_count": len(self.assets),
            "watchlist_count": len(self.watchlist),
        }

    def get_category_summary(self) -> Dict[str, Dict]:
        targets = self.config.get("targets", {})
        category_data: Dict[str, Dict] = {}

        for asset in self.assets:
            category = asset.category
            if category not in category_data:
                target_info = targets.get(category, {})
                category_data[category] = {
                    "name": target_info.get("name", category),
                    "description": target_info.get("description", ""),
                    "target_ratio": target_info.get("target_ratio"),
                    "total_value": 0.0,
                    "total_change": 0.0,
                    "assets": [],
                }

            category_data[category]["total_value"] += asset.current_value
            category_data[category]["total_change"] += asset.change
            category_data[category]["assets"].append(
                {
                    "id": asset.id,
                    "name": asset.name,
                    "ticker": asset.ticker,
                    "market": asset.market,
                    "asset_type": asset.asset_type,
                    "book_value": asset.book_value,
                    "current_value": asset.current_value,
                    "change": asset.change,
                    "change_rate": asset.change_rate,
                    "source": asset.source,
                    "note": asset.note or "",
                }
            )

        total_value = sum(item["total_value"] for item in category_data.values())
        for category, data in category_data.items():
            ratio = (data["total_value"] / total_value) if total_value > 0 else 0.0
            data["ratio"] = ratio * 100
            target_ratio = data["target_ratio"]
            data["gap_to_target"] = (
                (ratio - target_ratio) * 100 if target_ratio is not None else None
            )
            data["gap_value"] = (
                total_value * target_ratio - data["total_value"]
                if target_ratio is not None
                else None
            )

        for category, target_info in targets.items():
            if category not in category_data:
                target_ratio = target_info.get("target_ratio")
                category_data[category] = {
                    "name": target_info.get("name", category),
                    "description": target_info.get("description", ""),
                    "target_ratio": target_ratio,
                    "total_value": 0.0,
                    "total_change": 0.0,
                    "assets": [],
                    "ratio": 0.0,
                    "gap_to_target": -(target_ratio * 100) if target_ratio is not None else None,
                    "gap_value": total_value * target_ratio if target_ratio is not None else None,
                }

        return category_data

    def get_all_assets_table(self) -> List[Dict]:
        active_assets = sorted(self.assets, key=lambda asset: asset.current_value, reverse=True)

        return [
            {
                "id": asset.id,
                "name": asset.name,
                "symbol": asset.ticker,
                "market": asset.market,
                "type": asset.asset_type,
                "category": asset.category,
                "invested": asset.book_value,
                "change": asset.change,
                "current_value": asset.current_value,
                "change_rate": f"{asset.change_rate:.2f}%",
                "source": asset.source,
                "note": asset.note or "",
            }
            for asset in active_assets
        ]

    def get_watchlist_table(self) -> List[Dict]:
        return [asdict(item) for item in self.watchlist]

    def get_rebalance_priorities(self) -> List[Dict]:
        rows = []
        for category, data in self.get_category_summary().items():
            rows.append(
                {
                    "category": category,
                    "name": data["name"],
                    "current_ratio": data["ratio"],
                    "target_ratio": (
                        data["target_ratio"] * 100 if data["target_ratio"] is not None else None
                    ),
                    "current_value": data["total_value"],
                    "gap_value": data["gap_value"],
                }
            )

        return sorted(rows, key=lambda row: row["gap_value"] or float("-inf"), reverse=True)

    def print_summary(self):
        summary = self.get_portfolio_summary()
        categories = self.get_category_summary()
        priorities = self.get_rebalance_priorities()

        print("\n" + "=" * 80)
        print("投資ポートフォリオ サマリー")
        print("=" * 80)

        print("\n保有状況")
        print(f"  投資元本:        ¥{summary['total_invested']:,.0f}")
        print(f"  現在価値:        ¥{summary['total_value']:,.0f}")
        print(
            f"  損益:            ¥{summary['total_change']:,.0f} ({summary['overall_change_rate']:+.2f}%)"
        )
        print(f"  保有銘柄数:      {summary['active_assets_count']}")

        print("\nカテゴリ別配分")
        print("-" * 80)
        for _, data in sorted(
            categories.items(), key=lambda item: item[1]["total_value"], reverse=True
        ):
            target_ratio = data["target_ratio"]
            target_text = f"{target_ratio * 100:.1f}%" if target_ratio is not None else "-"
            gap_text = (
                f"{data['gap_to_target']:+.1f}pt" if data["gap_to_target"] is not None else "-"
            )
            print(
                f"  {data['name']:<18} 現在 {data['ratio']:>5.1f}% / 目標 {target_text:>6} / 差分 {gap_text:>7}"
            )

        if self.watchlist:
            print("\n監視リスト")
            print("-" * 80)
            for item in self.watchlist:
                budget = f"予算 ¥{item.planned_budget:,.0f}" if item.planned_budget else ""
                quantity = (
                    f"予定数量 {item.planned_quantity:g}" if item.planned_quantity else ""
                )
                details = " / ".join(part for part in [budget, quantity, item.note or ""] if part)
                print(f"  {item.name} ({item.ticker})  {details}")

        if priorities:
            print("\n比率ギャップ上位")
            print("-" * 80)
            for row in priorities[:5]:
                gap_value = row["gap_value"]
                if gap_value is None:
                    continue
                print(
                    f"  {row['name']:<18} ギャップ ¥{gap_value:>10,.0f} / 現在比率 {row['current_ratio']:>5.1f}%"
                )

        print("\n" + "=" * 80)

    def export_json(self, output_path: str = "data/portfolio_status.json"):
        summary = self.get_portfolio_summary()
        categories = self.get_category_summary()
        all_assets = self.get_all_assets_table()
        watchlist = self.get_watchlist_table()
        priorities = self.get_rebalance_priorities()

        data = {
            "summary": summary,
            "categories": {
                category: {
                    "name": item["name"],
                    "description": item["description"],
                    "target_ratio": item["target_ratio"],
                    "total_value": item["total_value"],
                    "total_change": item["total_change"],
                    "ratio": item["ratio"],
                    "gap_to_target": item["gap_to_target"],
                    "gap_value": item["gap_value"],
                }
                for category, item in categories.items()
            },
            "assets": all_assets,
            "watchlist": watchlist,
            "rebalance_priorities": priorities,
        }

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        print(f"\nデータをエクスポート: {output_path}")


if __name__ == "__main__":
    manager = PortfolioManager("config/portfolio.yaml")
    manager.print_summary()
    manager.export_json()
