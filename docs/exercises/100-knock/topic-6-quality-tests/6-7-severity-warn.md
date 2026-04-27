# 6-7: accepted_values に severity: warn を付け、違反 1 行混ざっても CI exit 0

## シナリオ

6-3 で `stg_products_100knock.category` に `accepted_values: [food, electronics, clothing, home, sports]` を
貼った。これは「この列の値域は 5 つの集合に閉じている」 という強い契約。
だが運用上は **「新カテゴリ追加直後の数日間、未登録カテゴリの行が混ざる」**
ような **過渡的な逸脱** がしばしば起こる。これを **CI 失敗 (exit 1)** で
止めると、毎朝の dbt build job が真っ赤になり、本当に直すべき他の問題が
WARN/ERROR 雑音に埋もれてしまう (= **警報疲れ / alert fatigue**)。

dbt は `severity: warn` (または `error_if: '>10'` のような閾値式) で
**「契約違反 = ERROR」 か 「契約違反 = WARN」 か** を **テスト 1 つずつ宣言**
できる。Step 1 では severity error (デフォルト) で 1 行違反を入れて FAIL を
体験し、Step 2 で `severity: warn` に切り替えて **同じ違反でも exit 0 で
WARN ログだけ** が出る挙動を確認する。

## 学べること

- `severity: warn` を test の `config:` 配下に書く構文
- WARN は **CI exit code = 0** を保つ → ジョブは緑のまま
- `dbt test` 出力の `Done. PASS=N WARN=1 ERROR=0 ... TOTAL=N+1` の読み方
- なぜ「重大度を test ごとに分ける」 のが運用 SLO の宣言になるのか
- `error_if: '>N'` / `warn_if: '>M'` で **閾値ベース** の重大度判定 (発展)

## 前提

- Topic ② ③ ④ ⑤ + Topic ⑥ 6-1〜6-5 完了
- 6-3 で `stg_products_100knock.category` に
  `accepted_values: ['food', 'electronics', 'clothing', 'home', 'sports']`
  が宣言されている (本問はその上に severity を被せる)

## 入力データ

`staging.stg_products_100knock` (100 行)。`category` は 6-3 で宣言済みの 5 値 enum。
本問では検証用に **1 行だけ** `category = 'paypay_pay'` のような **enum 違反値** を
混ぜた状態で、CI が止まらない (exit 0) ことを確認する。

## 課題

### Step 1: severity を意図的に外して FAIL を体験 (5 分)

`dbt/models/100-knock/topic-3/schema.yml` の `stg_products_100knock.category`
ブロックを **severity 未指定 = default error** のまま、違反データを挿入:

```sql
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.products SET category = 'unknown_category' WHERE product_id = 1;
SQL
```

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
```

期待: `accepted_values_*_category_*` が **FAIL**、`Done. PASS=N WARN=0 ERROR=1`
で **exit code != 0** (CI なら job が赤くなる)。

### Step 2: severity: warn に切り替え

schema.yml で `accepted_values` test に `config: severity: warn` を追加:

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
                severity: warn   # ← FAIL を WARN に格下げ
```

> **注意**: `arguments:` (test 引数) と `config:` (test 設定) は **兄弟ブロック**。
> 値の一覧は `arguments.values:`、severity は `config.severity:` に書く。混同しないこと。

### Step 3: 同じ違反データで再 test → WARN を確認

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
```

期待出力:

```text
... WARN  1 accepted_values_stg_products_100knock_category_food_electronics_clothing_home_sports ... [WARN 1 in 0.05s]
... 
Done. PASS=N WARN=1 ERROR=0 SKIP=0 TOTAL=N+1
```

`echo $?` → `0` (CI は緑のまま)。

### Step 4: ロールバック

検証データを戻して、本来の整合状態にする:

```sql
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'food' WHERE product_id = 1;"
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
# WARN=0 に戻る (severity: warn の宣言は schema.yml に残しておく)
```

## 完了条件

- [ ] schema.yml の `stg_products_100knock.category` の `accepted_values` に
      `config: severity: warn` が宣言されている
- [ ] `dbt parse` が成功する
- [ ] 違反 1 行を混ぜた状態で `dbt test --select stg_products_100knock` が
      **exit 0** (`echo $?` で 0)
- [ ] 同 `dbt test` 出力に `WARN=1` が含まれる (FAIL ではなく警告に降格)
- [ ] manifest 上で test の `config.severity` が `warn` になっている

## ヒント (詰まったら)

- **`config:` の位置**: `accepted_values:` 直下の `arguments:` と `config:` は
  並列。`config:` を `arguments:` の中に入れると引数として解釈されてエラー。
- **`severity: warn` vs `error_if`**:
  - `severity: warn` → 件数に関わらず 「違反があれば WARN」
  - `error_if: '>10'` → 「違反 11 件以上で ERROR、それ未満は WARN」
  - **閾値ベース** が欲しいときは `error_if` / `warn_if` を併用 (発展)。
- **CI exit code との関係**: dbt-core 1.x では WARN は exit code 0、ERROR は
  exit code 1。`severity: warn` は **「CI を止めない契約違反」** の宣言。
- **どんな test に warn を貼るべきか (運用設計)**:
  - **直すべきだが今すぐ止めるほどではない**: 過渡期の enum 追加、外部由来の
    型ゆらぎ、新規追加された source の信頼度がまだ低い時期
  - **重大度 ERROR を貼り続けるべき**: 主キー (`not_null` + `unique`)、参照整合
    (`relationships`)、契約 (contract: enforced) — これらは緩めると **下流が
    沈黙のうちに壊れる**
- **`dbt_test_passes` grader の挙動**: WARN は ERROR ではないので、grader は
  WARN を含む状態でも PASS 判定する (実装は `ERROR > 0` のみ NG)。本問の
  採点はこれを利用して「WARN を 1 件出しても test PASS と扱う」 設計。

## 解答例

詳細は [`6-7-severity-warn.solution.md`](6-7-severity-warn.solution.md) を参照。
