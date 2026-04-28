# 6-9: store_failures: true で失敗行を SQL で追え、修正→再 test→PASS まで 1 セッションで回す

## シナリオ

`dbt test` が `FAIL 5 in 0.06s` と出ても、ログには **「5 行失敗した」 という件数**
しか出ない。**「どの 5 行が失敗したか」** を知るには `target/run/.../<test>.sql` を
`cat` して psql で流し直す、という二度手間が必要。

dbt の test 設定 `store_failures: true` を貼ると、テストが返した違反行を
**Postgres のテーブル `dbt_test__audit.<test_name>`** に永続化してくれる。
失敗行を SELECT できるので、

1. **test FAIL** を観察
2. `dbt_test__audit.<test_name>` を `SELECT *` で **違反 5 行を直接確認**
3. raw を修正
4. `dbt test` 再実行 → **PASS に戻る**

という **デバッグループ** が SQL だけで完結する。本問はこの **「失敗行追跡 →
修正 → 再 test PASS」** のループを 1 セッションで完走する体験。

## 学べること

- `config: store_failures: true` を test に貼る構文
- 失敗行が保存される schema 名 (`dbt_test__audit`) と table 名 (`<test_name>`)
- psql で `\dn` / `\dt dbt_test__audit.*` で audit schema を覗く方法
- 「test FAIL → 失敗行 SELECT → raw 修正 → 再 test PASS」 の **完結ループ**
- なぜ store_failures が「データ品質運用の SLO」 を成立させるのか

## 前提

- Topic ② ③ ④ ⑤ + Topic ⑥ 6-1〜6-5 完了
- 6-3 で `stg_products_100knock.category` に `accepted_values` が貼られている
  (6-7 の severity: warn を貼っていてもよいが、本問では一時的に severity を
  外して FAIL を体験する。または別の test に store_failures を貼る)
- Postgres に `dbt_user` で接続できる (`docker exec` で psql が叩ける)

## 入力データ

`raw.products` (100 行)。本問は `category` 列に **5 行** の違反データを混ぜて、
それを `dbt_test__audit` から SELECT する流れ。

## 課題

### Step 1: schema.yml に store_failures: true を追加

`dbt/models/100-knock/topic-3/schema.yml` の `stg_products_100knock.category` の
`accepted_values` に `config: store_failures: true` を追加 (6-7 で
severity: warn を貼っている場合は **本問のために一時的に外す or severity: error
に戻す** — 失敗行を残しつつ FAIL の挙動を見たいため):

```yaml
  - name: stg_products_100knock
    columns:
      - name: category
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: ['food', 'electronics', 'clothing', 'home', 'sports']
              config:
                severity: error      # FAIL を体験したいので error に戻す
                store_failures: true # ← 失敗行を dbt_test__audit に保存
```

### Step 2: 違反データを混ぜる

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.products SET category = 'unknown_a' WHERE product_id = 1;
UPDATE raw.products SET category = 'unknown_b' WHERE product_id = 2;
UPDATE raw.products SET category = 'unknown_c' WHERE product_id = 3;
UPDATE raw.products SET category = 'unknown_d' WHERE product_id = 4;
UPDATE raw.products SET category = 'unknown_e' WHERE product_id = 5;
SQL
```

### Step 3: dbt test → FAIL を観察

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
# ... FAIL 5 accepted_values_stg_products_100knock_category_food_electronics_clothing_home_sports [FAIL 5 in 0.06s]
# ... Done. PASS=N WARN=0 ERROR=1 SKIP=0 TOTAL=N+1
```

### Step 4: dbt_test__audit から失敗行を SELECT

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
\dn dbt_test__audit
\dt dbt_test__audit.*
SELECT product_id, category
  FROM dbt_test__audit.accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports
 ORDER BY product_id;
SQL
```

期待: `product_id` 1〜5 の 5 行が `category = 'unknown_*'` として返ってくる。
**「どの行が違反か」 がデータとして見える** = デバッグの起点が手に入る。

### Step 5: raw を修正

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.products SET category = 'food'      WHERE product_id = 1;
UPDATE raw.products SET category = 'food'      WHERE product_id = 2;
UPDATE raw.products SET category = 'food'      WHERE product_id = 3;
UPDATE raw.products SET category = 'food'      WHERE product_id = 4;
UPDATE raw.products SET category = 'food'      WHERE product_id = 5;
SQL
```

### Step 6: 再 test → PASS

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
# ... Done. PASS=N+1 WARN=0 ERROR=0 SKIP=0 TOTAL=N+1
```

`dbt_test__audit.<test>` table は **次回 FAIL 時に上書きされる** (PASS 時は
更新されない)。手で残しておきたければそのまま、片付けたければ
`DROP SCHEMA dbt_test__audit CASCADE;` で消す。

## 完了条件

- [ ] schema.yml に `store_failures: true` が宣言されている
- [ ] `dbt parse` が成功する
- [ ] (採点後の手動確認) `dbt_test__audit` schema が dbt test 実行後に存在する
- [ ] 違反データを修正後、`dbt test --select stg_products_100knock` が PASS で終わる
- [ ] manifest 上で test の `config.store_failures` が true になっている

## ヒント (詰まったら)

- **`dbt_test__audit` schema が見つからない**: dbt-postgres は `--store-failures` を
  `<target.schema>_dbt_test__audit` schema に作る場合がある。本リポジトリは
  `get_custom_schema.sql` で prefix を打ち消しているので `dbt_test__audit` が
  直接できる。`\dn` で schema 一覧を確認。最初の `dbt test` 実行までは
  schema が作られないので注意 (本問の Step 4 が初回作成タイミング)。
- **失敗テーブルの命名規則**: `<test_name>` がそのまま table 名になる。
  `accepted_values` test は `accepted_values_<model>_<col>__<v1>__<v2>__...` の
  ように **値リストが連結される長い名前** になる。長すぎて困る場合は
  `name:` で明示すれば短縮可能 (例: `name: category_in_5_enum`)。
- **店舗運用上の注意 (= ストレージ消費)**: 全 test に `store_failures: true` を
  貼ると、失敗時にテーブルが大量にできてストレージを食う。本番では
  「**重要 test だけ**」 に貼るか、`dbt_project.yml` で **layer 単位** に
  ON/OFF (= 6-10 の主題)。
- **`store_failures_as: 'view'` (発展)**: dbt 1.4+ で、失敗行を view として
  保存することも可能。table より軽いが「snapshot 性が無い」 (次の test
  実行時に最新データを再評価する) ので、デバッグ用途は table のほうが安全。
- **CLI フラグでも同等**: `dbt test --store-failures` を CLI で渡しても同じ。
  schema.yml で宣言する利点は **「どの test に store_failures を貼っているか」 が
  コード上に残る** こと (= レビュー可能 / git blame 可能)。

## 解答例

詳細は [`6-9-store-failures-loop.solution.md`](6-9-store-failures-loop.solution.md) を参照。
