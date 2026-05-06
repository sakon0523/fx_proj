"""
ポートフォリオ可視化スクリプト
"""

import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt

# 日本語フォント設定
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False


class PortfolioVisualizer:
    """ポートフォリオ可視化クラス"""

    def __init__(self, data_path: str = "data/portfolio_status.json"):
        """
        Args:
            data_path: エクスポートされたJSONファイルのパス
        """
        self.data_path = Path(data_path)
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """JSONデータを読み込む"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def plot_category_pie(self, output_path: str = "data/portfolio_pie.png"):
        """カテゴリ別の円グラフ"""
        categories = self.data["categories"]

        keys = list(categories.keys())
        labels = [categories[key].get("name", key) for key in keys]
        values = [categories[key]["total_value"] for key in keys]
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        fig, ax = plt.subplots(figsize=(10, 8))
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90
        )

        # テキスト設定
        for text in texts:
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(9)
            autotext.set_weight("bold")

        ax.set_title("投資配分 (カテゴリ別)", fontsize=14, fontweight="bold", pad=20)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✅ 円グラフを保存: {output_path}")
        plt.close()

    def plot_top_assets_bar(
        self, output_path: str = "data/portfolio_bar.png", top_n: int = 10
    ):
        """上位資産の棒グラフ"""
        assets = self.data["assets"][:top_n]

        names = [a["name"] for a in assets]
        values = [a["current_value"] for a in assets]
        changes = [a["change"] for a in assets]

        # 色を変動に応じて決定
        colors = ["green" if c >= 0 else "red" for c in changes]

        fig, ax = plt.subplots(figsize=(12, 8))
        bars = ax.barh(names, values, color=colors, alpha=0.7)

        # 値をラベルとして表示
        for i, (bar, val, chg) in enumerate(zip(bars, values, changes)):
            ax.text(val, i, f"  ¥{val:,.0f} ({chg:+.0f})", va="center", fontsize=9)

        ax.set_xlabel("現在価値 (¥)", fontsize=11)
        ax.set_title(
            "投資資産 Top 10 (現在価値)", fontsize=14, fontweight="bold", pad=20
        )
        ax.invert_yaxis()
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✅ 棒グラフを保存: {output_path}")
        plt.close()

    def plot_asset_performance(
        self, output_path: str = "data/portfolio_performance.png", top_n: int = 8
    ):
        """資産のパフォーマンス比較（変動率）"""
        assets = sorted(
            self.data["assets"],
            key=lambda x: float(x["change_rate"].strip("%")),
            reverse=True,
        )[:top_n]

        names = [a["name"] for a in assets]
        rates = [float(a["change_rate"].strip("%")) for a in assets]

        colors = ["green" if r >= 0 else "red" for r in rates]

        fig, ax = plt.subplots(figsize=(12, 6))
        bars = ax.bar(range(len(names)), rates, color=colors, alpha=0.7)

        # ラベル設定
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_ylabel("変動率 (%)", fontsize=11)
        ax.set_title(
            "資産パフォーマンス Top 8 (変動率)", fontsize=14, fontweight="bold", pad=20
        )
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.8)
        ax.grid(axis="y", alpha=0.3)

        # 値をラベルとして表示
        for bar, rate in zip(bars, rates):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{rate:.2f}%",
                ha="center",
                va="bottom" if height >= 0 else "top",
                fontsize=9,
            )

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✅ パフォーマンスグラフを保存: {output_path}")
        plt.close()

    def plot_portfolio_summary(self, output_path: str = "data/portfolio_summary.png"):
        """ポートフォリオサマリーグラフ"""
        summary = self.data["summary"]

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

        # 1. 元本と現在価値
        labels1 = ["投資元本", "評価損益"]
        values1 = [summary["total_invested"], abs(summary["total_change"])]
        colors1 = ["#66B2FF", "#7BC96F" if summary["total_change"] >= 0 else "#FF7F7F"]
        ax1.pie(values1, labels=labels1, autopct="%1.1f%%", colors=colors1)
        ax1.set_title("元本と評価損益", fontweight="bold")

        # 2. 元本と現在価値の比較
        ax2.bar(
            ["投資元本", "現在価値"],
            [summary["total_invested"], summary["total_value"]],
            color=["#66B2FF", "#7BC96F"],
            alpha=0.7,
        )
        ax2.set_ylabel("金額 (¥)", fontsize=10)
        ax2.set_title(
            f"保有評価: ¥{summary['total_value']:,.0f}",
            fontweight="bold",
        )
        for index, value in enumerate([summary["total_invested"], summary["total_value"]]):
            ax2.text(index, value, f"¥{value:,.0f}", ha="center", va="bottom")

        # 3. 損益率
        change_rate = summary["overall_change_rate"]
        ax3.barh(
            ["損益率"],
            [change_rate],
            color="#7BC96F" if change_rate >= 0 else "#FF7F7F",
            alpha=0.7,
        )
        lower_bound = min(change_rate, 0) - 5
        upper_bound = max(change_rate, 0) + 5
        ax3.set_xlim([lower_bound, upper_bound])
        ax3.set_xlabel("%", fontsize=10)
        ax3.set_title(f"損益率: {change_rate:+.2f}%", fontweight="bold")
        ax3.text(change_rate, 0, f"  {change_rate:+.2f}%", va="center")

        # 4. 資産額推移（テキスト表示）
        summary_text = f"""
現在価値: ¥{summary['total_value']:,.0f}
保有銘柄数: {summary['active_assets_count']}

投資成績:
  元本: ¥{summary['total_invested']:,.0f}
  損益: ¥{summary['total_change']:,.0f}
  利益率: {summary['overall_change_rate']:+.2f}%
監視銘柄数: {summary['watchlist_count']}
        """
        ax4.text(
            0.1,
            0.5,
            summary_text,
            fontsize=11,
            verticalalignment="center",
        )
        ax4.axis("off")

        plt.suptitle(
            "投資ポートフォリオ サマリー", fontsize=16, fontweight="bold", y=0.98
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✅ サマリーグラフを保存: {output_path}")
        plt.close()

    def generate_all_plots(self):
        """すべてのグラフを生成"""
        print("\n📊 グラフ生成中...\n")
        self.plot_portfolio_summary()
        self.plot_category_pie()
        self.plot_top_assets_bar()
        self.plot_asset_performance()
        print("\n✅ すべてのグラフが生成されました\n")


if __name__ == "__main__":
    visualizer = PortfolioVisualizer("data/portfolio_status.json")
    visualizer.generate_all_plots()
