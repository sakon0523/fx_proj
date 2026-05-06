#!/usr/bin/env python3
"""
SBI証券の保有商品CSVを portfolio.private.yaml 形式へ変換する。
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml


ENCODINGS = ("cp932", "shift_jis", "utf-8-sig", "utf-8")
HEADER_KEY = "銘柄コード・ティッカー"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="assetbalance CSV を portfolio.private.yaml 形式へ変換"
    )
    parser.add_argument("csv_path", help="SBI証券の assetbalance CSV パス")
    parser.add_argument(
        "--public-config",
        default="config/portfolio.yaml",
        help="銘柄ID対応を読む公開設定YAML",
    )
    parser.add_argument(
        "--output",
        default="config/portfolio.private.yaml",
        help="出力先 YAML",
    )
    return parser.parse_args()


def load_csv_rows(csv_path: Path) -> List[dict]:
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as file:
                rows = list(csv.reader(file))
            break
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    else:  # pragma: no cover - fallback path
        raise RuntimeError(f"CSV を開けませんでした: {last_error}")

    header_index = None
    for index, row in enumerate(rows):
        if HEADER_KEY in row:
            header_index = index
            break

    if header_index is None:
        raise RuntimeError("CSV ヘッダー行を検出できませんでした。")

    header = rows[header_index]
    data_rows = rows[header_index + 1 :]
    records: List[dict] = []

    for row in data_rows:
        if not row or all(not cell.strip() for cell in row):
            continue
        padded = row + [""] * (len(header) - len(row))
        records.append(dict(zip(header, padded)))

    return records


def load_public_holdings(config_path: Path) -> list[dict]:
    if not config_path.exists():
        return []
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return config.get("portfolio", {}).get("holdings", [])


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def normalize_ticker(value: str) -> str:
    value = (value or "").strip().upper()
    if value.endswith(".T"):
        value = value[:-2]
    return value


def normalize_account(value: str) -> str:
    return normalize_name(value)


def build_id_map(holdings: Iterable[dict]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in holdings:
        asset_id = item.get("id")
        if not asset_id:
            continue

        ticker = normalize_ticker(str(item.get("ticker", "")))
        account = normalize_account(str(item.get("account_type", "")))
        if ticker:
            mapping[f"ticker:{ticker}"] = asset_id
            if account:
                mapping[f"ticker_account:{ticker}:{account}"] = asset_id

        name = normalize_name(str(item.get("name", "")))
        if name:
            mapping[f"name:{name}"] = asset_id
            if account:
                mapping[f"name_account:{name}:{account}"] = asset_id

    return mapping


def parse_number(value: str) -> Optional[float]:
    text = (value or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    return float(text)


def infer_asset_id(row: dict, id_map: Dict[str, str]) -> str:
    ticker = normalize_ticker(row.get("銘柄コード・ティッカー", ""))
    name = normalize_name(row.get("銘柄", ""))
    account = normalize_account(row.get("口座", ""))
    if ticker and account and f"ticker_account:{ticker}:{account}" in id_map:
        return id_map[f"ticker_account:{ticker}:{account}"]
    if name and account and f"name_account:{name}:{account}" in id_map:
        return id_map[f"name_account:{name}:{account}"]
    if ticker and f"ticker:{ticker}" in id_map:
        return id_map[f"ticker:{ticker}"]
    if name and f"name:{name}" in id_map:
        return id_map[f"name:{name}"]

    if ticker:
        return ticker.lower().replace(".", "_")
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unknown"


def build_private_item(row: dict, asset_id: str) -> Optional[dict]:
    asset_type = (row.get("種別") or "").strip()
    if asset_type in {"外貨預り", "外貨預り金"}:
        return None

    quantity = parse_number(row.get("保有数量", ""))
    average_cost = parse_number(row.get("平均取得価額", ""))
    current_price = parse_number(row.get("現在値", ""))
    current_value_jpy = parse_number(row.get("時価評価額[円]", ""))
    profit_jpy = parse_number(row.get("評価損益[円]", ""))
    unit = (row.get("［単位］", "") or "").strip()

    item: dict = {"id": asset_id}

    if quantity is not None:
        item["quantity"] = int(quantity) if quantity.is_integer() else quantity
    if average_cost is not None:
        item["average_cost"] = average_cost
    if current_price is not None:
        item["current_price"] = current_price

    if asset_type == "投資信託":
        item["unit_base"] = 10000

    if unit == "USD" and quantity and average_cost and current_value_jpy is not None and profit_jpy is not None:
        book_value_jpy = current_value_jpy - profit_jpy
        if book_value_jpy > 0:
            item["cost_fx_rate"] = round(book_value_jpy / (quantity * average_cost), 6)

    if len(item) == 1 and current_value_jpy is not None and profit_jpy is not None:
        book_value_jpy = current_value_jpy - profit_jpy
        item["manual_book_value"] = book_value_jpy
        item["manual_current_value"] = current_value_jpy

    return item


def order_items(items: list[dict], holdings: list[dict]) -> list[dict]:
    order = {item.get("id"): index for index, item in enumerate(holdings)}
    return sorted(items, key=lambda item: order.get(item["id"], 10**6))


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_path)
    public_config = Path(args.public_config)
    output_path = Path(args.output)

    rows = load_csv_rows(csv_path)
    holdings = load_public_holdings(public_config)
    id_map = build_id_map(holdings)

    items: list[dict] = []
    for row in rows:
        asset_id = infer_asset_id(row, id_map)
        item = build_private_item(row, asset_id)
        if item is not None:
            items.append(item)

    ordered = order_items(items, holdings)
    payload = {"portfolio": {"holdings": ordered}}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, allow_unicode=True, sort_keys=False)

    print(f"Converted {csv_path} -> {output_path}")


if __name__ == "__main__":
    main()
