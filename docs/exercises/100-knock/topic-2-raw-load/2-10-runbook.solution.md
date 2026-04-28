# 2-10 解答例

## docs/exercises/100-knock/topic-2-raw-load/runbook.md (新規)

```markdown
# Topic ② Runbook: raw 投入 → freshness 確認 → dbt build

このドキュメントは「dbt build を走らせる前に必ずやるべき手順」を順序付きで固めたもの。
新規メンバがジョインした翌週でも、この通りにコマンドを叩けば Topic ② までの状態を再現できることを目標にする。

dbt の `pre-hook` (model 単位の SQL フック) とは別レイヤーの話で、ここでは
「**dbt そのものを走らせる前の人間側の手順**」を runbook 化している。

---

## Prerequisites

1. リポジトリを clone してリポジトリルートで作業
2. `.env` を作成 (`.env.example` をコピーして DB 接続情報を埋める)
3. PostgreSQL を起動: `docker compose up -d postgres`
4. Python 仮想環境を有効化: `source .venv/bin/activate` (もしくは `.venv/bin/python` を都度使う)
5. 依存パッケージ: `uv pip install -r requirements.txt` (psycopg, dbt-postgres, faker, pandas, python-dotenv)

---

## Steps

### 1. generate — ダミーデータを生成

```bash
.venv/bin/python scripts/generate_dummy_data.py
# Topic ① で書いた個別 generator を使う場合:
# .venv/bin/python scripts/100-knock/topic-1/generate_1_1_customers.py
# ... (1-2, 1-3, 1-4 と続ける)
```

期待出力: `data/raw/{customers,products,stores,orders}.csv` (または `data/100-knock/topic-1/`) が作成される。
**シードを固定しているので 2 回実行しても md5sum が変わらないことを確認 (冪等性)**。

### 2. load — raw schema に投入

```bash
.venv/bin/python scripts/load_raw_data.py
# Topic ② 2-1 の loader を使う場合:
# .venv/bin/python scripts/100-knock/topic-2/load_2_1_raw.py
```

期待出力:

```
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows
```

検証: `psql "$DATABASE_URL" -c "SELECT count(*) FROM raw.orders;"` で行数を目視確認。

### 3. freshness — `dbt source freshness` で鮮度契約をチェック

```bash
cd dbt
../.venv/bin/dbt source freshness --profiles-dir .
```

期待出力: `PASS freshness of raw.orders [PASS in 0.05s]`。
ここで `WARN` / `ERROR` が出たら、**build に進まずに上流データの更新を待つ**。
これが「freshness を build の前に挟む」運用の核心 — 上流が古いまま build しても無駄なので、ここでフェイルファストする。

### 4. build — `dbt build` で staging 以下を構築

```bash
cd dbt
../.venv/bin/dbt build --profiles-dir .
```

期待出力: `Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N`。

---

## Verification (各ステップの成功確認)

| Step | 検証コマンド | 期待値 |
|---|---|---|
| 1. generate | `wc -l data/raw/customers.csv` | 1001 (header + 1000) |
| 2. load | `psql "$DATABASE_URL" -c "select count(*) from raw.orders"` | 10000 |
| 3. freshness | `dbt source freshness` exit code | 0 |
| 4. build | `dbt build` exit code | 0 |

---

## Troubleshooting

### `dbt source freshness` が WARN を返す

→ raw データが古い。Step 1-2 を再実行して最新 timestamp で投入し直す。

### `psycopg.OperationalError: connection refused`

→ Postgres コンテナが起動していない。`docker compose ps` で確認、未起動なら `docker compose up -d postgres`。

### `Compilation Error: dbt found two sources with the name "raw"`

→ 2-7 で別名 source を入れたとき `name: raw` で重複宣言した。`name: raw_alt` に直す。

### `dbt build` で incremental model がフルリフレッシュされる

→ Topic ④ で扱う話。本トピックの範囲では `dbt build --full-refresh` で意図的に再構築する。

---

## `pre-hook` との関係 (補足)

- dbt の `pre-hook` / `post-hook`: **model 単位** で build 直前/直後に SQL を流す (例: GRANT、テンポラリ index)
- 本 runbook: **dbt 全体** を走らせる前の人間/CI ステップ (= `dbt build` を走らせる前段)

両者は対象スコープが違う。Topic ⑨ で `pre-hook` の本格的な使い方を扱うので、そこと混同しないように。
```

**ポイント (runbook 自体の設計について)**:

- **コピペ即動**: コマンドは fenced code block + 絶対 or `cd dbt` 起点で書く。「自分のターミナル環境を察して書き換えて」と読み手に依頼してはいけない。
- **順序の理由を明示**: 単に手順を並べるだけでなく、「なぜこの順序か」を 1-2 行添える。これが運用知識の蓄積。
- **検証ステップを別表に**: 各ステップが成功したかを機械的に確認できる SQL/コマンドを表で並べると、CI 化したときにそのまま step 化できる。
- **トラブルシュート**: 「自分が踏んだ罠」を必ず書き残す。次の人が踏むのを防げる。
- **`pre-hook` 参照**: 補足セクションで dbt の `pre-hook` と本 runbook の違いに 1 行触れる。これで Topic ⑨ への伏線にもなる。

## 解説まとめ

- **なぜ runbook を書く？**: 「dbt が触らない領域」(generate, load, env) は YAML/manifest に記録できないので、Markdown で人間が読める形に固めるしかない。これを書かないと「セットアップ手順は誰かの頭の中」になり、ジョイン/オフボードのたびに knowledge silo が起きる。
- **dbt の `pre-hook` との違い**: `pre-hook` は model 単位の SQL フック (例: `pre-hook: "GRANT SELECT ON {{ this }} TO analyst"`)。本 runbook は **dbt そのものを走らせる前の人間の手順**。スコープが違う。「`pre-`」という接頭辞が同じなので混同しがちだが、対象が違うことを明示しておくと Topic ⑨ で `pre-hook` を扱うときに混乱しない。
- **freshness を build の前に置く意義**: 上流データが古いまま `dbt build` を走らせると、staging/mart は最新化されているように見えて中身が前日のまま、という「**鮮度の隠蔽**」が起きる。`source freshness` を build の前段に置くと、ここでフェイルファストできる。
- **CI への写経**: runbook がきちんと書けると、その内容をそのまま `.github/workflows/grade.yml` の `steps:` に写経できる:
  ```yaml
  - name: Generate dummy data
    run: .venv/bin/python scripts/generate_dummy_data.py
  - name: Load raw
    run: .venv/bin/python scripts/load_raw_data.py
  - name: Source freshness
    run: cd dbt && ../.venv/bin/dbt source freshness --profiles-dir .
  - name: Build
    run: cd dbt && ../.venv/bin/dbt build --profiles-dir .
  ```
  人間用 (runbook) と機械用 (CI yaml) の対応関係を意識すると、両者を同期させる習慣がつく。
- **後続トピックでの活かし方**: Topic ⑨ で `pre-hook` / `post-hook` を model に張る演習があるが、その時に「**hook で書ける範囲 / runbook で書く範囲**」の境界線を判断できるようになる。SQL で書けて model 単位で完結するなら hook、外部プロセスを跨ぐなら runbook、という線引き。
- **runbook を更新する責務**: 手順を変えたら runbook も同時に直す、というのが ops の鉄則。CI を追加したときにも runbook の `Verification` 表に項目を追加する。「runbook が嘘をつく状態」が一番悪い。
