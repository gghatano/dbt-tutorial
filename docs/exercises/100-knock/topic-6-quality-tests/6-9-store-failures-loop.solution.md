# 6-9 解答例

## dbt/models/100-knock/topic-3/schema.yml (stg_products_100knock 部分)

```yaml
version: 2

models:
  # ... (他 model はそのまま)

  - name: stg_products_100knock
    description: "Type-cast staging view of raw.products. category は lower(trim(...)) で正規化済み。"
    columns:
      - name: product_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: product_name
      - name: category
        description: |
          5 値の closed enum。
          store_failures: true で違反行を dbt_test__audit に永続化し、
          失敗 → SELECT → 修正 → 再 test PASS のループを SQL で完結させる。
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: ['food', 'electronics', 'clothing', 'home', 'sports']
              config:
                severity: error            # 本問は FAIL を体験したいので error
                store_failures: true       # ← 失敗行を dbt_test__audit に保存
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null
```

**ポイント**:

- **`config:` 配下に store_failures**: severity と並列。`store_failures: true` を
  test 単位で ON にする。CLI から `--store-failures` を渡す方法もあるが、
  schema.yml に書く方が **コードレビュー対象** になる (= 「失敗行を残す重要 test」 が
  git history に残る)。
- **6-7 との関係**: 6-7 で同じ `accepted_values` を `severity: warn` にしていた
  場合、本問では一時的に `severity: error` に戻して FAIL を体験する。学習の
  順番として「警告 → 失敗 → 失敗追跡 → 修正」 の流れが一気通貫になる。
  完了後は 6-7 の severity: warn を復元するか、本問の宣言を残すかは設計判断。

## 違反データの注入 → dbt test → 失敗行 SELECT → 修正 → 再 test PASS

### Step 2: 違反データを 5 行混ぜる

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.products SET category = 'unknown_a' WHERE product_id = 1;
UPDATE raw.products SET category = 'unknown_b' WHERE product_id = 2;
UPDATE raw.products SET category = 'unknown_c' WHERE product_id = 3;
UPDATE raw.products SET category = 'unknown_d' WHERE product_id = 4;
UPDATE raw.products SET category = 'unknown_e' WHERE product_id = 5;
SQL
UPDATE 1
UPDATE 1
UPDATE 1
UPDATE 1
UPDATE 1
```

### Step 3: dbt test → FAIL

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
04:00:00  Running with dbt=1.11.x
04:00:01  Found 11 models, 5 sources, 80 data tests, ...
04:00:02  N of M START test accepted_values_stg_products_100knock_category... [RUN]
04:00:02  N of M FAIL 5 accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports [FAIL 5 in 0.06s]
04:00:02    See test failures:
04:00:02      SELECT * FROM dbt_test__audit.accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports
04:00:02  
04:00:02  Done. PASS=N WARN=0 ERROR=1 SKIP=0 TOTAL=N+1
```

dbt が **「失敗行を見るための SELECT 文」 を親切にログに出してくれる** ことに
注目。これがあるから「コピペ → 流す」 だけでデバッグ起点に到達できる。

### Step 4: 失敗行を SELECT

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
\dn dbt_test__audit
\dt dbt_test__audit.*
SELECT product_id, category
  FROM dbt_test__audit.accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports
 ORDER BY product_id;
SQL
       List of schemas
       Name       |  Owner
------------------+----------
 dbt_test__audit  | dbt_user

                                              List of relations
      Schema      |                                       Name                                       | Type
------------------+----------------------------------------------------------------------------------+-------
 dbt_test__audit  | accepted_values_stg_products_100knock_category__food__electronics__clothing__... | table

 product_id | category
------------+-----------
          1 | unknown_a
          2 | unknown_b
          3 | unknown_c
          4 | unknown_d
          5 | unknown_e
(5 rows)
```

「**どの 5 行が違反か**」 がデータとして手に入る。raw のどの行を直せばよいかが
即決まる。

### Step 5: raw を修正

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.products SET category = 'food' WHERE product_id IN (1, 2, 3, 4, 5);
SQL
UPDATE 5
```

### Step 6: 再 test → PASS

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
... 
N of M PASS accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports [PASS]
... 
Done. PASS=N+1 WARN=0 ERROR=0 SKIP=0 TOTAL=N+1
```

PASS に戻った。`dbt_test__audit.<test>` table は **次回 FAIL 時に上書き**
されるまで残る (PASS 時は更新されない仕様)。手で消したければ:

```sql
DROP SCHEMA dbt_test__audit CASCADE;
```

## manifest で store_failures を確認

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
key = [k for k in m['nodes'] if 'accepted_values_stg_products_100knock_category' in k][0]
print('store_failures:', m['nodes'][key]['config'].get('store_failures'))
"
store_failures: True
```

## 解説まとめ

- **なぜ store_failures か (= 「失敗の二度手間」 を消す)**:
  - dbt 標準ログは「件数」 しか出ない。違反行を見るには `target/run/.../*.sql` を
    cat → psql で再実行 → 結果を読む、という **3 ステップ** が必要。
  - `store_failures: true` で **「最後の dbt test 実行時の違反行」 が** 既に
    Postgres にあり、`SELECT *` 1 本で見える。**デバッグ起点までの距離が短くなる**。
- **デバッグループの完結**:
  ```text
  [test FAIL] → [dbt_test__audit を SELECT] → [raw 修正] → [再 test PASS]
       ↑                                                          │
       └──────────────────────────────────────────────────────────┘
  ```
  このループが **SQL だけで完結** する (Python / シェルスクリプト不要)。
  運用エンジニアでもアナリストでも回せる。
- **「テストとデバッグの依存関係を閉じる」 の意味**:
  - 通常: test FAIL → SQL 起動 → ファイル探す → 別ツール呼ぶ → 結果を別画面で見る
  - store_failures あり: test FAIL → SQL 1 本で完了
  - 「test 対象のデータ」 と 「test 失敗の証拠」 が同じ Postgres 内に居る
    = **データの世界の中で完結する**。
- **dbt_test__audit schema の挙動**:
  - 初回 `dbt test --store-failures` で schema が作られる
  - 各 test ごとに table ができる (`<test_name>` 名)
  - **次回 FAIL 時に上書き** (`CREATE OR REPLACE`)、PASS 時は更新なし
  - PASS が続けば「最後の FAIL の証拠」 が残り続ける → 履歴は持たない設計
    (履歴が欲しければ別途 hook で snapshot)
- **本リポジトリの schema 命名 (`get_custom_schema.sql` の効き目)**:
  - dbt-postgres デフォルト: `<target.schema>_dbt_test__audit` (例: `staging_dbt_test__audit`)
  - 本リポジトリ: `get_custom_schema.sql` で prefix を打ち消しているので
    **`dbt_test__audit`** に直接できる。`\dn` で確認。
- **次の 6-10 への接続**:
  - 本問は **test 1 個ずつ** に `store_failures: true` を貼った
  - 6-10 では `dbt_project.yml` の `data_tests:` ブロックで **layer 単位** に
    一括宣言できることを学ぶ (staging 全 test に store_failures: true、mart には
    付けない、等の運用ポリシーをコードで宣言)。
- **store_failures が成立させる「データ品質 SLO」**:
  - 「test 落ちた」 だけでなく **「どこが落ちたか」 が常時 SQL で見える** 状態
    = **観測可能性 (observability)** がある。
  - SLO 「データ品質違反は 24 時間以内に修正」 のような目標を掲げる時、
    違反の証拠が即時 SELECT できることが運用判断の前提になる。
  - dbt の test を **「コードに付随する単体テスト」 ではなく 「運用される SLO」**
    に格上げする中核機能。
