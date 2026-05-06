"""
ルールベースの異常検知エンジン
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import yaml

from portfolio_manager import PortfolioManager


class SignalEngine:
    """保有商品の異常検知"""

    def __init__(
        self,
        config_path: str = "config/portfolio.yaml",
        price_snapshot_path: str = "data/price_snapshot.json",
    ):
        self.config_path = Path(config_path)
        self.price_snapshot_path = Path(price_snapshot_path)
        self.config = self._load_config()
        self.snapshot = self._load_snapshot()
        self.manager = PortfolioManager(
            config_path=str(self.config_path),
            price_snapshot_path=str(self.price_snapshot_path),
        )
        self.monitoring = self.config.get("monitoring", {})

    def _monitoring_defaults(self) -> dict:
        defaults = self.monitoring.get("defaults")
        if isinstance(defaults, dict):
            return defaults

        # Backward compatibility with the old flat monitoring schema.
        return {
            "daily_move_alert_pct": self.monitoring.get("daily_move_alert_pct", 5.0),
            "volume_spike_ratio": self.monitoring.get("volume_spike_ratio", 2.0),
            "rsi_lower": self.monitoring.get("rsi_lower", 30.0),
            "rsi_upper": self.monitoring.get("rsi_upper", 70.0),
            "category_daily_move_alert_pct": self.monitoring.get(
                "category_daily_move_alert_pct", 3.0
            ),
            "category_min_assets": self.monitoring.get("category_min_assets", 2),
        }

    def _category_monitoring(self, category: str) -> dict:
        return self.monitoring.get("categories", {}).get(category, {})

    def _asset_monitoring(self, asset_id: str) -> dict:
        return self.monitoring.get("assets", {}).get(asset_id, {})

    def _effective_monitoring(self, category: str | None = None, asset_id: str | None = None) -> dict:
        settings = dict(self._monitoring_defaults())
        if category is not None:
            settings.update(self._category_monitoring(category))
        if asset_id is not None:
            settings.update(self._asset_monitoring(asset_id))
        return settings

    def _load_config(self) -> dict:
        with self.config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def _load_snapshot(self) -> dict:
        if not self.price_snapshot_path.exists():
            return {}

        with self.price_snapshot_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _holding_snapshot(self, asset_id: str) -> dict:
        return self.snapshot.get("holdings", {}).get(asset_id, {})

    def _build_asset_signals(self) -> List[Dict]:
        signals: List[Dict] = []

        for asset in self.manager.assets:
            snapshot_item = self._holding_snapshot(asset.id)
            if not snapshot_item:
                continue

            rules = self._effective_monitoring(category=asset.category, asset_id=asset.id)
            daily_move_alert_pct = float(rules.get("daily_move_alert_pct", 5.0))
            volume_spike_ratio = float(rules.get("volume_spike_ratio", 2.0))
            price_up_min_pct = float(rules.get("price_up_min_pct", 2.0))
            atr_alert_multiplier = float(rules.get("atr_alert_multiplier", 2.0))
            rsi_lower = float(rules.get("rsi_lower", 30.0))
            rsi_upper = float(rules.get("rsi_upper", 70.0))

            daily_change_pct = snapshot_item.get("daily_change_pct")
            if daily_change_pct is not None and abs(daily_change_pct) >= daily_move_alert_pct:
                direction = "上昇" if daily_change_pct > 0 else "下落"
                severity = (
                    "high" if abs(daily_change_pct) >= daily_move_alert_pct * 1.5 else "medium"
                )
                signals.append(
                    {
                        "type": "daily_move",
                        "severity": severity,
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} が前日比 {daily_change_pct:+.2f}% の{direction}",
                        "metrics": {"daily_change_pct": daily_change_pct},
                    }
                )

            atr_14_pct = snapshot_item.get("atr_14_pct")
            if (
                daily_change_pct is not None
                and atr_14_pct is not None
                and atr_14_pct > 0
                and abs(daily_change_pct) >= atr_14_pct * atr_alert_multiplier
            ):
                signals.append(
                    {
                        "type": "atr_move",
                        "severity": "high",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": (
                            f"{asset.name} の変動率 {daily_change_pct:+.2f}% が "
                            f"ATR基準 {atr_14_pct * atr_alert_multiplier:.2f}% を超えています"
                        ),
                        "metrics": {
                            "daily_change_pct": daily_change_pct,
                            "atr_14_pct": atr_14_pct,
                            "atr_alert_multiplier": atr_alert_multiplier,
                        },
                    }
                )

            volume_ratio = snapshot_item.get("volume_ratio")
            if volume_ratio is not None and volume_ratio >= volume_spike_ratio:
                signals.append(
                    {
                        "type": "volume_spike",
                        "severity": "medium",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} の出来高が20日平均の {volume_ratio:.2f} 倍",
                        "metrics": {"volume_ratio": volume_ratio},
                    }
                )

            if (
                daily_change_pct is not None
                and volume_ratio is not None
                and daily_change_pct >= price_up_min_pct
                and volume_ratio >= volume_spike_ratio
            ):
                signals.append(
                    {
                        "type": "price_up_volume_spike",
                        "severity": "high",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": (
                            f"{asset.name} が {daily_change_pct:+.2f}% 上昇し、"
                            f"出来高も20日平均の {volume_ratio:.2f} 倍です"
                        ),
                        "metrics": {
                            "daily_change_pct": daily_change_pct,
                            "volume_ratio": volume_ratio,
                        },
                    }
                )

            current_price = snapshot_item.get("current_price")
            sma_50 = snapshot_item.get("sma_50")
            sma_200 = snapshot_item.get("sma_200")
            if current_price is not None and sma_50 is not None and current_price < sma_50:
                signals.append(
                    {
                        "type": "below_sma_50",
                        "severity": "low",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} が50日移動平均を下回っています",
                        "metrics": {"current_price": current_price, "sma_50": sma_50},
                    }
                )
            if current_price is not None and sma_200 is not None and current_price < sma_200:
                signals.append(
                    {
                        "type": "below_sma_200",
                        "severity": "medium",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} が200日移動平均を下回っています",
                        "metrics": {"current_price": current_price, "sma_200": sma_200},
                    }
                )

            rsi_14 = snapshot_item.get("rsi_14")
            if rsi_14 is not None and rsi_14 <= rsi_lower:
                signals.append(
                    {
                        "type": "rsi_oversold",
                        "severity": "medium",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} の RSI(14) が {rsi_14:.1f} で売られ過ぎ圏",
                        "metrics": {"rsi_14": rsi_14},
                    }
                )
            elif rsi_14 is not None and rsi_14 >= rsi_upper:
                signals.append(
                    {
                        "type": "rsi_overbought",
                        "severity": "low",
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "message": f"{asset.name} の RSI(14) が {rsi_14:.1f} で過熱圏",
                        "metrics": {"rsi_14": rsi_14},
                    }
                )

        return signals

    def _build_category_signals(self) -> List[Dict]:
        signals: List[Dict] = []

        grouped: Dict[str, List[dict]] = {}
        for asset in self.manager.assets:
            snapshot_item = self._holding_snapshot(asset.id)
            daily_change_pct = snapshot_item.get("daily_change_pct")
            if daily_change_pct is None:
                continue
            grouped.setdefault(asset.category, []).append(
                {
                    "name": asset.name,
                    "daily_change_pct": daily_change_pct,
                }
            )

        for category, items in grouped.items():
            rules = self._effective_monitoring(category=category)
            threshold = float(rules.get("category_daily_move_alert_pct", 3.0))
            min_assets = int(rules.get("category_min_assets", 2))
            if len(items) < min_assets:
                continue

            average_move = sum(item["daily_change_pct"] for item in items) / len(items)
            if abs(average_move) >= threshold:
                direction = "上昇" if average_move > 0 else "下落"
                asset_names = ", ".join(item["name"] for item in items)
                signals.append(
                    {
                        "type": "category_move",
                        "severity": "high" if average_move < 0 else "medium",
                        "category": category,
                        "message": (
                            f"{category} カテゴリが平均 {average_move:+.2f}% の{direction} "
                            f"({asset_names})"
                        ),
                        "metrics": {"average_daily_change_pct": average_move, "asset_count": len(items)},
                    }
                )

        return signals

    def generate_signals(self) -> Dict:
        asset_signals = self._build_asset_signals()
        category_signals = self._build_category_signals()
        all_signals = asset_signals + category_signals

        severity_order = {"high": 0, "medium": 1, "low": 2}
        all_signals.sort(key=lambda item: severity_order.get(item["severity"], 9))

        return {
            "generated_at": self.snapshot.get("fetched_at"),
            "signals": all_signals,
            "summary": {
                "total": len(all_signals),
                "high": sum(1 for item in all_signals if item["severity"] == "high"),
                "medium": sum(1 for item in all_signals if item["severity"] == "medium"),
                "low": sum(1 for item in all_signals if item["severity"] == "low"),
            },
        }

    def print_signals(self):
        result = self.generate_signals()
        print("\n" + "=" * 80)
        print("異常検知シグナル")
        print("=" * 80)

        summary = result["summary"]
        print(
            f"\n件数: total={summary['total']} / high={summary['high']} / medium={summary['medium']} / low={summary['low']}"
        )

        if not result["signals"]:
            print("\n異常シグナルは検出されませんでした。")
            print("\n" + "=" * 80)
            return

        print("\nシグナル一覧")
        print("-" * 80)
        for item in result["signals"]:
            print(f"  [{item['severity']}] {item['message']}")

        print("\n" + "=" * 80)

    def export_json(self, output_path: str = "data/signals.json") -> dict:
        result = self.generate_signals()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print(f"\nシグナルをエクスポート: {output_path}")
        return result


if __name__ == "__main__":
    engine = SignalEngine()
    engine.print_signals()
    engine.export_json()
