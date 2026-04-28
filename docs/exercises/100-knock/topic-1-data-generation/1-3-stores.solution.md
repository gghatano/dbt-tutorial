# 1-3 解答例

## scripts/100-knock/topic-1/generate_1_3_stores.py

```python
"""Generate stores.csv (20 rows) for 100-knock Topic 1 / Q3.

`prefecture` is constrained to the closed set of 47 Japanese prefectures so
that downstream geographic aggregations are free of label noise.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 42
LOCALE = "ja_JP"
NUM_STORES = 20

# All 47 prefectures, north to south.
PREFECTURES = (
    "北海道",
    "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県",
    "沖縄県",
)
assert len(PREFECTURES) == 47, "PREFECTURES must contain exactly 47 entries"

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "data" / "100-knock" / "topic-1" / "stores.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    rows = []
    for store_id in range(1, NUM_STORES + 1):
        store_name = f"店舗{store_id:02d}_{fake.last_name()}"
        prefecture = rng.choice(PREFECTURES)
        rows.append(
            {
                "store_id": store_id,
                "store_name": store_name,
                "prefecture": prefecture,
            }
        )

    df = pd.DataFrame(rows, columns=["store_id", "store_name", "prefecture"])
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")


if __name__ == "__main__":
    main()
```

**ポイント**:

- `PREFECTURES` を **47 件のタプルで全列挙** + `assert len(PREFECTURES) == 47` の self-check。Python 起動時に件数違いを即検知する低コストな防御。
- 既存 `scripts/generate_dummy_data.py` には 20 県分しか入っていないので、それを **そのまま使うと採点が不安定** になる。Topic ① では 47 県の完全集合を新たに宣言することで「店舗が西日本・九州にもあり得る」現実を表現する。
- 20 件しか作らないので `random.choices` (重み付き) ではなく素直な `random.choice` で十分。重複は **許可** されている (= 同県に複数店舗があるのは普通)。
- `f"店舗{store_id:02d}_{fake.last_name()}"` で "店舗01_鈴木" のような店名を作る。`store_id` は連番なので zero-padded 2 桁で表示しても自然。

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_3_stores.py
Generated data/100-knock/topic-1/stores.csv: 20 rows

$ wc -l data/100-knock/topic-1/stores.csv
      21 data/100-knock/topic-1/stores.csv

$ head -3 data/100-knock/topic-1/stores.csv
store_id,store_name,prefecture
1,店舗01_中島,熊本県
2,店舗02_佐々木,富山県

# 採点 shell_command の発想: 47 県外が 0 行であることを wc -l で確認
$ awk -F, 'NR>1 {print $3}' data/100-knock/topic-1/stores.csv \
    | grep -vxE "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県" \
    | wc -l | tr -d ' '
0
```

## 解説まとめ

- **47 県を完全列挙**: enum のサイズが大きくても **コードで全列挙** することで「ぱっと見でホワイトリスト」になる。これは表記揺れを根本から防ぐ最強の手段。
- **assert で件数 self-check**: タプルから 1 県落ちる/重複が紛れ込む事故を Python 起動時に殺す。テストではなくモジュール初期化時の防御。
- **重複前提**: PK は `store_id` で一意。`prefecture` は重複可なので `expect_unique` ではなく **値域チェックのみ** が責務。
- **shell_command + grep -v + wc -l のイディオム**: 「ホワイトリスト外を `grep -vxE` で残し、その行数が 0 なら OK」というパターンは csv_assert で表現しづらい値域チェックの定番。`tr -d ' '` で BSD/GNU `wc -l` の余白差を吸収する。
- **MVP 流用に注意**: `scripts/generate_dummy_data.py` の `PREFECTURES` (20 県) を import せず、**Topic ① 用に独立した完全集合** を宣言する。MVP の都合で県数を増減すると採点が壊れるカップリングを避けるため。
