# 1-8 解答例

## scripts/100-knock/topic-1/generate_1_8_nullable_comments.py

```python
"""Generate reviews.csv (2,000 rows) with ~10% NULL comments for 100-knock Topic 1 / Q8.

The NULL ratio is intentional: real review data has rating-only entries.
Downstream schema.yml should reflect this by NOT putting `not_null` on `comment`.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 208
LOCALE = "ja_JP"
NUM_REVIEWS = 2_000
NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NULL_COMMENT_PROB = 0.10  # 10% of reviews carry no comment.

# Reference timestamp window: ~200 days back from a hard-coded reference moment.
REFERENCE_DATETIME = datetime(2026, 4, 26, 23, 59, 59)
LOOKBACK_DAYS = 200

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "data" / "100-knock" / "topic-1" / "reviews.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    rows = []
    null_count = 0
    for review_id in range(1, NUM_REVIEWS + 1):
        customer_id = rng.randint(1, NUM_CUSTOMERS)
        product_id = rng.randint(1, NUM_PRODUCTS)
        rating = rng.randint(1, 5)

        # The defining declaration: ~10% of comments are NULL by design.
        if rng.random() < NULL_COMMENT_PROB:
            comment = None
            null_count += 1
        else:
            # Strip embedded newlines so the CSV stays one-row-per-line.
            comment = fake.text(max_nb_chars=80).replace("\n", " ").strip()

        # Spread posted_at across LOOKBACK_DAYS, second resolution.
        seconds_back = rng.randint(0, LOOKBACK_DAYS * 86_400 - 1)
        posted_at = (REFERENCE_DATETIME - timedelta(seconds=seconds_back)).isoformat(
            timespec="seconds"
        )

        rows.append(
            {
                "review_id": review_id,
                "customer_id": customer_id,
                "product_id": product_id,
                "rating": rating,
                "comment": comment,
                "posted_at": posted_at,
            }
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "review_id",
            "customer_id",
            "product_id",
            "rating",
            "comment",
            "posted_at",
        ],
    )
    # to_csv writes None / NaN as empty string by default — exactly what
    # Postgres `COPY ... FORMAT CSV` interprets as NULL.
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    ratio = null_count / NUM_REVIEWS * 100
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")
    print(f"comment NULL ratio: {ratio:.1f}% ({null_count} / {NUM_REVIEWS})")


if __name__ == "__main__":
    main()
```

**ポイント**:

- `if rng.random() < 0.10:` の素直な分岐で「10% NULL」を実装。`rng.choices` で重み付けしてもよいが、
  読み手に意図が伝わるのは `random()` + 閾値の方
- `comment = None` を入れて pandas の `to_csv` に任せると、CSV 上は空フィールド (`,,`) になる。
  Postgres の `COPY ... FORMAT CSV` はこれを **NULL として読み込む** ので、後の raw ロードで
  自然に NULL 行になる。`na_rep="NULL"` でリテラル文字列 `NULL` を書く流派もあるが、
  COPY のデフォルトと噛み合わないので **空文字派が標準**
- `fake.text(max_nb_chars=80).replace("\n", " ")` は CSV の行構造を壊さないための防御。Faker の
  text は文末で改行を入れることがあるので必須
- `posted_at` を秒精度で振っているのは、後の `posted_at::timestamp` キャストが (timezone なしの)
  Postgres `timestamp` 型と整合するため。マイクロ秒は不要
- `null_count` を集計して末尾に出すことで、シード差で 10% から大きくズレていないか即座に目視確認できる

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_8_nullable_comments.py
Generated data/100-knock/topic-1/reviews.csv: 2000 rows
comment NULL ratio: 10.3% (206 / 2000)

$ wc -l data/100-knock/topic-1/reviews.csv
    2001 data/100-knock/topic-1/reviews.csv

$ head -3 data/100-knock/topic-1/reviews.csv
review_id,customer_id,product_id,rating,comment,posted_at
1,479,7,5,バナーインチカレッジオークション...,2025-11-29T06:58:34
2,710,28,3,彼必要ボトル野球風景細かい建築再現する。,2026-03-03T19:14:58

$ awk -F, 'NR>1 {if ($5 == "") n++; t++} END {printf "null=%d total=%d ratio=%.1f%%\n", n, t, n/t*100}' \
    data/100-knock/topic-1/reviews.csv
null=206 total=2000 ratio=10.3%
```

## 解説まとめ

- **なぜ NULL を 10% 混ぜるのか**: 本物のレビューデータには「星だけ付けて文章なし」が必ずある。
  生成段階でこの実態を再現しておかないと、`dbt test` が常に「ハッピーパス」だけを通すように
  なってしまい、本物データを流した瞬間に大量の `not_null` 違反で破綻する。
  **生成データに現実の歪みを混ぜることで、テストが本物の品質チェックになる**
- **`not_null` テストを comment に付けないのが正解**: schema.yml で `not_null` を全列に
  ベタ付けする学習者を抑止する材料。NULL 許容は **データ仕様** であり、テストで禁止してしまうと
  仕様と検査が矛盾する。NULL を許すなら **明示的に許す** と書く (= テストを書かない、または
  `tests: []` で空配列を明示) のが正しい設計
- **採点 YAML の `expect_no_nulls` リスト**: `review_id, customer_id, product_id, rating, posted_at`
  の 5 列だけを並べ、`comment` は **意図的に外す**。学習者が「全列に no_nulls を付ければ高得点」と
  誤解するのを防ぎ、「**NULL を許すべき列を見極める**」という設計判断そのものを問う構造になっている
- **空文字 vs リテラル NULL**: CSV における NULL の表現は標準化されていない。Postgres COPY のデフォルト
  (空文字 = NULL) と pandas のデフォルト (`na_rep=""`) が一致しているのは偶然ではなく、両エコシステムが
  「区切り文字の間に何もない = NULL」という最小公倍数の合意に従っているため。`na_rep="NULL"` を
  使うと `'NULL'` という文字列の値と区別できなくなる罠がある
- **シード固定の安心感**: NULL 比率は確率的に揺れるが、シード `208` 固定なら毎回同じ NULL 行集合が出る。
  これにより「先週は 10.3% だったのに今週は 9.5% でテスト落ちる」という事故を防げる
- **`posted_at` を秒精度で振る**: 2000 行を 200 日 (= 17M 秒) に振るので衝突確率はほぼ 0。
  `posted_at` を distinct PK 候補として後で使うこともできる (本問では PK は `review_id` だが)
