# 1-10 解答例

## scripts/100-knock/topic-1/generate_1_10_stats.py

```python
"""Profile all CSVs under data/100-knock/topic-1/ and write _stats.json.

This is a self-managed "data contract": rows / columns / null_ratio per file.
Sits *upstream* of dbt source freshness / dbt-expectations.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "100-knock" / "topic-1"
OUTPUT_PATH = DATA_DIR / "_stats.json"


def _profile_csv(csv_path: Path) -> dict:
    """Single-pass scan: row count, column list, per-column null ratio."""
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        null_counts = {col: 0 for col in columns}
        row_count = 0
        for row in reader:
            row_count += 1
            for col in columns:
                value = row.get(col)
                # CSV NULL convention: empty string == null
                if value is None or value == "":
                    null_counts[col] += 1

    if row_count == 0:
        null_ratio = {col: 0.0 for col in columns}
    else:
        null_ratio = {col: round(null_counts[col] / row_count, 6) for col in columns}

    return {
        "rows": row_count,
        "columns": columns,
        "null_ratio": null_ratio,
    }


def main() -> int:
    if not DATA_DIR.exists():
        print(f"ERROR: data dir missing: {DATA_DIR}", file=sys.stderr)
        print("  -> Run 1-1 〜 1-8 first to produce input CSVs.", file=sys.stderr)
        return 1

    files: dict[str, dict] = {}
    # sorted() so JSON output order is stable -> diff-friendly
    for csv_path in sorted(DATA_DIR.glob("*.csv")):
        # Defensive: skip dotfiles or anything starting with '_'
        if csv_path.name.startswith("_"):
            continue
        files[csv_path.name] = _profile_csv(csv_path)

    if not files:
        print(f"ERROR: no CSV found under {DATA_DIR}", file=sys.stderr)
        print("  -> Run 1-1 〜 1-8 first.", file=sys.stderr)
        return 1

    stats = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(files)} files profiled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**ポイント**:

- **標準ライブラリのみ**: `csv` + `json` + `pathlib` だけで完結。pandas を入れない理由は (1) CI の依存を減らす (2) `null_ratio` のような単純集計に DataFrame は過剰 (3) CSV の NULL 規約 (空文字 = NULL) を `csv.DictReader` の素直な挙動で扱える。
- **1-pass 集計**: ファイルを 2 回読まない (`row_count` と `null_counts` を同じループで埋める)。10,000 行レベルでは差は出ないが、将来 10M 行になったときの正解パターン。
- **`sorted(glob('*.csv'))`**: ファイル列挙順を辞書順に固定。これで JSON の `files` キーの順序が安定 → 差分レビューが楽になる。
- **`_stats.json` 自身を除外**: そもそも `glob('*.csv')` で `.json` は引っかからないが、念のため `name.startswith("_")` で防御。将来 `_metadata.csv` のような特殊ファイルを置いたときも壊れない。
- **`generated_at` は現在時刻で OK**: 1-9 と違い、これは「観測時刻」のメタデータ。冪等にする意味がない (毎回観測時刻が変わるのが正しい)。むしろ stats の鮮度を後から確認できるよう毎回更新する方が運用に資する。
- **`ensure_ascii=False`**: 日本語列名 (将来拡張) でも壊れないように。
- **`round(..., 6)`**: float の表示桁を抑えて diff 安定化。

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_10_stats.py
Wrote data/100-knock/topic-1/_stats.json: 5 files profiled

$ cat data/100-knock/topic-1/_stats.json | python3 -m json.tool | head -30
{
  "generated_at": "2026-04-28T10:30:00Z",
  "files": {
    "customers.csv": {
      "rows": 1000,
      "columns": [
        "customer_id",
        "customer_name",
        "email",
        "created_at"
      ],
      "null_ratio": {
        "customer_id": 0.0,
        "customer_name": 0.0,
        "email": 0.0,
        "created_at": 0.0
      }
    },
    "orders.csv": {
      "rows": 10000,
      "columns": [...],
      "null_ratio": {...}
    },
    "reviews.csv": {
      "rows": 2000,
      "columns": [..., "comment", ...],
      "null_ratio": {"comment": 0.1, ...}
    }
  }
}

$ python3 -c "import json; s=json.load(open('data/100-knock/topic-1/_stats.json')); print(s['files']['customers.csv']['rows'])"
1000
```

## 解説まとめ

- **なぜ自前 data contract を持つ?**: dbt の `source freshness` や `dbt-expectations` は **DB に取り込まれた後** にしか動かない。「そもそも CSV の段階で 1000 行ない」「`comment` の null 率が 10% ではなく 95% に膨れた」という事故を、**取り込み前** に検知するためのレイヤーが要る。それが `_stats.json`。
- **dbt-expectations と何が違う?**:
  - **観測ポイント**: dbt-expectations は warehouse 上の table に対して走る (`expect_column_values_to_not_be_null` 等)。`_stats.json` は CSV に対して走る。
  - **実行タイミング**: dbt-expectations は `dbt test`。`_stats.json` は CSV 生成直後。
  - **責務**: dbt-expectations は「変換後のデータが期待を満たしているか」、`_stats.json` は「**入力 CSV の形そのもの**」。前者の **前段** に位置する。
  - **依存**: dbt-expectations は dbt + warehouse + パッケージ依存が必要。`_stats.json` は Python 標準ライブラリだけ。CI が壊れた状態でも単体で観測できる。
- **`_stats.json` の使い道 (後続トピックの予告)**:
  - **静的レビュー**: PR で `_stats.json` が diff に出れば、上流のデータ形が変わった瞬間にレビュアーが気付ける。
  - **回帰検出**: 過去の `_stats.json` をリポジトリに保存しておき、CI で「行数が前回比 50% 落ちたら fail」のような健全性チェックに使える。
  - **dbt source.freshness との接続**: `generated_at` を `loaded_at` 相当のメタとして source.yml に渡し、freshness 判定の根拠にできる。
- **「pandas で書きたくなる気持ち」を抑える**: 標準ライブラリだけで成立するスクリプトは依存破綻に強い。Python 3.x が動けば必ず動く ≒ 5 年後の自分が読んでも動かせる。これが上流ユーティリティの設計指針。
- **「冪等じゃなくていいの?」**: 1-9 と違い、本問の `generated_at` は意図的に毎回更新する。CSV の中身が変わっていなくても観測時刻だけは進める = 「いつ最後にプロファイルしたか」をトラッキングできる。冪等性とトレーサビリティはトレードオフで、ここは後者を取る判断。
