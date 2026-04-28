# 1-9: 生成スクリプトに `--rows` / `--date` 引数を追加して複数日分を冪等に再生成

## シナリオ

1-4 で作った `orders.csv` 1 ファイル運用は、本番運用には耐えない。実務では「2026-04-15 分のデータをもう一回作り直したい」「直近 7 日分だけ再生成したい」という要求が日常的に来る。
今回は 1-4 の `generate_1_4_orders.py` を改修して、`--rows N` と `--date YYYY-MM-DD` を CLI で受け取り、`data/100-knock/topic-1/orders_<date>.csv` という **日付ごとに別ファイル** を出力するスクリプトに進化させる。
キモは「**同じ引数で 2 回呼んだら 1 バイトも変わらない (md5sum 一致)**」という冪等性。これが後続トピックで `dbt run --full-refresh` を安全に走らせる前提条件になる。

## 学べること

- `argparse` で日付・行数を受け取り、`date.fromisoformat()` でバリデーション
- 日付文字列から **決定論的なシード** を導出 (`hashlib.sha1(date).digest()` の先頭 4 bytes)
- `Faker.seed_instance(seed)` + `random.Random(seed)` の 2 系統シードで日替わり再現性を担保
- 同じ引数 → バイト同一出力という「**入力の冪等性**」契約
- 後続の `--full-refresh` / 部分再ロードを安全にする上流側の設計

## 前提

- 1-4 (orders 10,000 行) を完了済み (`scripts/100-knock/topic-1/generate_1_4_orders.py` がある)
- `requirements.txt` から `Faker` / `pandas` インストール済み
- 出力先 `data/100-knock/topic-1/` は 1-1〜1-8 で既に作られているはず (なくても script が `mkdir -p`)

## 入力データ

不要。学習者が新規 CLI 改修するだけ。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_9_orders_cli.py` を作る (1-4 を踏襲しつつ CLI を載せた新規ファイル。既存 1-4 はそのまま温存)。

要件:

- CLI: `--date YYYY-MM-DD` (必須) と `--rows N` (デフォルト 1000) を受け取る
- 出力: `data/100-knock/topic-1/orders_<date>.csv` (例: `orders_2026-04-15.csv`)
- 列: `order_id`, `order_date`, `customer_id`, `product_id`, `store_id`, `quantity`, `unit_price`
- `order_date` は `--date` で指定した日付に固定
- **シードは日付から決定論的に導出**: `seed = int.from_bytes(hashlib.sha1(date_str.encode()).digest()[:4], "big")`
- `Faker.seed_instance(seed)` + `random.Random(seed)` を両方かける
- `order_id` は日付ごとに **被らない** ように `pk_start = 100_000 + offset_days * (--rows の上限見込み) + i` のように設計 (詰まったらヒント参照)
- 出力ディレクトリは `pathlib.Path.mkdir(parents=True, exist_ok=True)`

### Step 2: 実行

```bash
# 同じ引数で 2 回 → md5sum 一致を確認
python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-15 --rows 500
md5sum data/100-knock/topic-1/orders_2026-04-15.csv
python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-15 --rows 500
md5sum data/100-knock/topic-1/orders_2026-04-15.csv
# 2 つの md5 が同じになるはず

# 別日付なら別ファイル
python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-16 --rows 500
ls data/100-knock/topic-1/orders_*.csv
# orders_2026-04-15.csv  orders_2026-04-16.csv
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-9-cli-args.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_9_orders_cli.py` が存在する
- [ ] `--date 2026-04-15 --rows 500` で `orders_2026-04-15.csv` が出力される (header + 500 行)
- [ ] 同じコマンドを 2 回呼ぶと出力 CSV の md5sum が完全一致する
- [ ] `--date` を変えると別ファイルが出力される (上書きしない)
- [ ] `--rows 100` で 100 行になる (CLI 引数が反映されている)

## ヒント (詰まったら)

- **強い参考実装**: `scripts/exercises/generate_03_new_orders.py` が既に「`--date` + `--rows` + 日付派生 seed + per-date 別ファイル」を実装済み。argparse の構成・seed 導出ロジック・PK 衝突回避のオフセット計算をそのまま読んで真似していい (テーマ的に正解の見本)。
- **シード導出**: `hashlib.sha1(args.date.encode("utf-8")).digest()[:4]` を `int.from_bytes(_, "big")` で 32-bit 整数化すると、同じ日付なら必ず同じ seed、違う日付なら別 seed が出る。
- **PK 衝突回避**: `pk_start = 100_000 + (target_date - date(2026, 4, 26)).days * 10_000 + 1` のように、日付ごとに 10,000 件分のレンジを予約する設計にしておくと、後で日次マージしても `order_id` が衝突しない。
- **`Faker.seed_instance` だけだと足りない**: pandas や純 `random` を内部で使うと、それらは Faker の seed の影響を受けない。`random.Random(seed)` を別に用意してそれを使い回すのが鉄則。
- **冪等性の罠**: `datetime.now()` を 1 行でも混ぜると即座に冪等性が壊れる。「実行時刻」「OS の locale」「Python のバージョン依存の dict 順」を一切混ぜない。

## 解答例

詳細は [`1-9-cli-args.solution.md`](1-9-cli-args.solution.md) を参照。
