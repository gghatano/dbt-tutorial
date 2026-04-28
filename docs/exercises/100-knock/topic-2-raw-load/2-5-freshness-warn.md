# 2-5: 故意に `loaded_at` を過去にして `dbt source freshness` の WARN を発生させる

## シナリオ

2-4 で `freshness:` を宣言したが、ロード直後の `loaded_at` は **常に新鮮** なので
SLA 違反が起きない。今回は故意に `raw.orders.loaded_at` を **36 時間前** に書き換え、
`dbt source freshness` を回して **WARN が発出される**ことを確認する。

これは「契約は宣言しただけでは死んでいる」という事実を体で確かめる演習。実データで warn を踏み抜く
ことで、Topic ② で書いた `freshness:` が本当に防壁として機能していることを確信できる。

## 学べること

- `dbt source freshness` の判定ロジック (現在時刻 - `MAX(loaded_at)` を warn/error と比較)
- WARN を発生させるための **狙った値域** (1 day < age < 2 day)
- `dbt source freshness` の exit code: WARN=0 / ERROR=1 (warn は警告で job は通る)
- WARN ログの形 (`WARN freshness of raw_100knock.orders`) と grep での検証
- データを弄って "失敗パスを意図的に踏む" CI テストパターン

## 前提

- 2-1 / 2-2 / 2-3 / 2-4 完了
- `raw.orders` がロード済みで `loaded_at` 列が新鮮 (= 現在時刻に近い)
- `dbt source freshness --select source:raw_100knock.orders` が **直前は PASS** だった状態

## 入力データ

`raw.orders.loaded_at` を 36 時間前 (1.5 day) に書き換える。1 day < 36h < 2 day なので
`warn_after: 1 day` を超え、`error_after: 2 day` には届かない → **WARN** が出る。

## 課題

### Step 1: `loaded_at` を過去に書き換える小スクリプトを書く

`scripts/100-knock/topic-2/age_orders.py` を新規作成する。

要件:

- `.env` から DSN を組み立てる (2-1 の `_build_dsn` と同じ)
- `psycopg.connect` で接続し、以下の SQL を実行:
  ```sql
  UPDATE raw.orders SET loaded_at = now() - interval '36 hours';
  ```
- commit して終了。stdout に「Aged X rows」と件数を出す

### Step 2: 実行

```bash
set -a; source .env; set +a
python3 scripts/100-knock/topic-2/age_orders.py
# Aged 10000 rows

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT now() - max(loaded_at) AS age FROM raw.orders;"
# age | 1 day 12:00:00 (前後) -- 1 day を超え、2 day 未満
```

### Step 3: `dbt source freshness` で WARN を踏む

```bash
cd dbt
../.venv/bin/dbt source freshness --profiles-dir . \
  --select source:raw_100knock.orders 2>&1 | tee /tmp/freshness.log

grep -q WARN /tmp/freshness.log && echo "WARN detected, OK"
echo "exit=$?"
```

期待: ログに `WARN freshness of raw_100knock.orders` が出現し、`dbt source freshness` 自体は
**exit 0** (warn は警告だから run は通る)。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-5-freshness-warn.grading.yaml
```

採点は warn が出たことを `grep -q WARN` で確認する shell_command チェックで行う。

### Step 5: 後片付け (任意)

```bash
python3 scripts/100-knock/topic-2/load_raw.py
# 再ロードで loaded_at が DEFAULT now() に戻り PASS 状態に
```

## 完了条件

- [ ] `scripts/100-knock/topic-2/age_orders.py` が存在する
- [ ] スクリプト実行が exit 0
- [ ] `raw.orders.loaded_at` の最大値が **24 時間以上前** になっている
- [ ] `dbt source freshness --select source:raw_100knock.orders` の出力に `WARN` が含まれる
- [ ] 上記コマンド自体は exit 0 で終わる (warn は警告)

## ヒント (詰まったら)

- **WARN と ERROR の境目**: `interval '36 hours'` (= 1.5 day) は安全に warn 領域。
  もっと過去 (`interval '3 days'`) にすると ERROR になり、`dbt source freshness` が exit 1 を返す。
  本問では「warn を踏みたい」のでちょうど 1.5 day を狙う。
- **`now() - interval '36 hours'`**: Postgres の `now()` は **トランザクション開始時刻** なので、
  10,000 行に同じ値が入る。`loaded_at TIMESTAMPTZ` の TZ も自動で付く。
- **WARN の検出**: `dbt source freshness` の stdout は ANSI カラーコードを含むことがあるが、
  `WARN` という文字列はそのまま含まれるので `grep -q WARN` で拾える。
- **exit code に頼らない**: WARN 時の exit code は 0 (PASS と同じ)。なので「warn が出たか」は
  **stdout の文字列マッチ**で判定するしかない。これが本問の重要ポイント。
- **本番 CI への展開**: `dbt source freshness --warn-error` を付けると warn も exit 1 にできる。
  「warn でも止めたい」厳格運用ならこのフラグ。

## 解答例

詳細は [`2-5-freshness-warn.solution.md`](2-5-freshness-warn.solution.md) を参照。
