# 7-8: dbt build --select +int_... で snapshot → ref → test を一気通貫

## シナリオ

7-7 で `int_orders_with_historical_price_100knock` を作り、`ref('snap_products_100knock')`
で snapshot を DAG に組み込んだ。これで `dbt build --select +<consumer>`
を叩くと、dbt が **依存解析して snapshot から走らせてくれる** はずだ。

`dbt build` は 1 コマンドで `snapshot` → `run` → `test` をトポロジカル順に
実行する **総合コマンド**。 `dbt run` だけだと snapshot は走らないし、
`dbt snapshot` だけだと下流 model は更新されない。**運用ではこの 1 本で全部
動かすのが原則**で、CI / 本番 cron もこの形になる。

本問では実際に `dbt build --select +int_orders_with_historical_price_100knock`
を実行し、ログに `snapshot` ステップ → `model` ステップ → `test` ステップが
順に出ることを確認、結果を md に保存する。

## 学べること

- `dbt build` が snapshot / model / test を 1 本で扱う総合コマンドであること
- `--select +<node>` で「**この node の上流すべて + この node**」を選択する記法
- snapshot がトポロジカルに **model より先** に走る順序保証
- ログを成果物として残す習慣 (= 後で「あの日 build は通っていたか」を遡れる)

## 前提

- 7-1 〜 7-7 完了 (snap_products_100knock + int_orders_with_historical_price_100knock 揃い)
- `dbt parse` が通る
- `set -a; source .env; set +a` 済みで dbt が DB 接続できる

## 入力データ

不要。既存の DAG をそのまま `dbt build` するだけ。

## 課題

### Step 1: dbt build を実行してログを保存

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --profiles-dir . \
    --select +int_orders_with_historical_price_100knock \
    2>&1 | tee /tmp/build-7-8.log
cd ..
```

ログ末尾に `Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N` が出れば成功。
ログ中に少なくとも 1 行 `snapshot` ステップ
(例: `OK snapshotted snapshots.snap_products_100knock`) が含まれていることを確認。

### Step 2: build-log.md に保存

`docs/exercises/100-knock/topic-7-snapshot/build-log.md` を新規作成し、以下を含める:

- 実行コマンド (`dbt build --select +int_orders_with_historical_price_100knock`)
- ログ全文または要約 (snapshot / model / test 各ステップの行を含む 30〜100 行)
- 「`dbt run` だけ叩いていたら何が違ったか」の 1〜2 行考察
  (= snapshot が走らないので int 側の `unit_price` が古いままになる、など)

```bash
# 雰囲気
cp /tmp/build-7-8.log docs/exercises/100-knock/topic-7-snapshot/build-log.md
# 先頭にコマンドと考察セクションを手で追記
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-7-snapshot/7-8-dbt-build-snap.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-7-snapshot/build-log.md` が存在する
- [ ] log 中に `snapshot` ステップが含まれている
- [ ] log 中に `int_orders_with_historical_price_100knock` の model ステップが含まれている
- [ ] 採点で `dbt build --select +int_orders_with_historical_price_100knock` が exit 0 で完走

## ヒント (詰まったら)

- **`dbt build` で snapshot が走らない**: `+` プレフィックスを忘れていないか
  確認。`--select int_orders_with_historical_price_100knock` (= `+` なし)
  だと **その node 単体しか走らない**。`+<node>` で「上流全部 + 自分」、
  `<node>+` で「自分 + 下流全部」、`+<node>+` で両方。
- **snapshot ステップが `SELECT 0` と出る**: snapshot 1 回目が既に走っている、
  かつ raw.products が変わっていない正常な no-op (= 7-9 の主題)。失敗ではない。
- **`dbt build` が test 失敗で ERROR**: snapshot や model が PASS していても
  test が落ちると build は ERROR で終わる。これは **総合コマンドが各ステージ
  を直列に検証してくれる** ありがたい挙動。schema.yml の test を見直す。
- **log 行数が膨大**: 必要なステップ (`snapshot ... OK`, `view model ... OK`,
  `test ... PASS`) だけ抜粋して md に貼っても OK。全文添付は不要。
- **`tee` でログが空になる**: dbt は色付き ANSI で出すので、`--no-colors`
  を渡すと plain text になりやすい (任意)。

## 解答例

詳細は [`7-8-dbt-build-snap.solution.md`](7-8-dbt-build-snap.solution.md) を参照。
