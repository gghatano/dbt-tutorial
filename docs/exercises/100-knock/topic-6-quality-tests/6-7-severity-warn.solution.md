# 6-7 解答例

## dbt/models/100-knock/topic-3/schema.yml (stg_products_100knock 部分)

6-3 で書いた `accepted_values` test に `config: severity: warn` を追加:

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
          正規化済み category (lower + trim)。
          値域は 5 値の closed enum だが、運用上の過渡期 (新カテゴリ追加直後 etc.) を
          考慮して severity: warn に格下げ。CI が落ちず、WARN ログで気付ける運用。
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: ['food', 'electronics', 'clothing', 'home', 'sports']
              config:
                severity: warn
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null
```

**ポイント**:

- **`arguments:` と `config:` は並列**: `accepted_values:` 直下に `arguments:`
  (test 自身の引数: 値リスト等) と `config:` (test の振る舞い: severity / store_failures /
  enabled / where 等) を 2 つ並べる。順序は問わない。
- **`severity: warn` の意味**: dbt は test 結果が「違反行 > 0」 でも、severity が
  warn の test を **「FAIL ではなく WARN」** として集計する。WARN は dbt の
  exit code 0 に分類される (= CI ジョブは緑のまま)。
- **description で warn 化の根拠を残す**: 「なぜ category だけ warn か?」 を
  6 ヶ月後にレビュアーが追えるよう、業務的根拠を YAML に書く。「過渡期の
  運用緩和」 と書いておけば、新カテゴリ追加が落ち着いた段階で **warn を
  外して strict に戻す** という運用判断もしやすい。

## dbt/models/100-knock/topic-3/schema.yml の宣言まとめ

`stg_products_100knock.category` の test は **2 段構え**:

1. **`not_null` (severity: error デフォルト)** — NULL は絶対許さない
2. **`accepted_values` (severity: warn)** — enum 違反は WARN だけ

「NULL は構造的におかしい (= 絶対 ERROR)」 と「値域逸脱は業務的に許容しうる
(= 警告のみ)」 を **同じ列の隣り合う test で重大度を変える** のが運用設計の妙。

## 違反データを混ぜた実行例

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'unknown_category' WHERE product_id = 1;"
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
04:00:00  Running with dbt=1.11.x
04:00:01  Found 11 models, 5 sources, 80 data tests, ...
04:00:02  1 of N START test not_null_stg_products_100knock_product_id ........... [RUN]
04:00:02  1 of N PASS  not_null_stg_products_100knock_product_id ............... [PASS]
... (中略) ...
04:00:03  N of N START test accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports [RUN]
04:00:03  N of N WARN  1 accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports [WARN 1 in 0.05s]
04:00:03  
04:00:03  Done. PASS=N WARN=1 ERROR=0 SKIP=0 NO-OP=0 TOTAL=N+1

$ echo $?
0
```

WARN 1 件が出ても **exit code 0** で終わる。CI ログに警告が残るので
人間は気付けるが、**ジョブは赤くならない**。

## 比較: severity: warn なしの場合 (Step 1 の挙動)

同じ違反データで severity 宣言を外すと:

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
... 
N of N FAIL 1 accepted_values_stg_products_100knock_category__food__electronics__clothing__home__sports [FAIL 1 in 0.05s]
... 
Done. PASS=N WARN=0 ERROR=1 SKIP=0 TOTAL=N+1

$ echo $?
1
```

`ERROR=1` で **exit code 1** → CI ジョブ赤。

## manifest で severity を確認

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
key = [k for k in m['nodes'] if 'accepted_values_stg_products_100knock_category' in k][0]
print('severity:', m['nodes'][key]['config']['severity'])
"
severity: warn
```

`'severity': 'warn'` が確認できる。

## ロールバック

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'food' WHERE product_id = 1;"
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
... Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

WARN=0 に戻る (severity: warn の宣言は schema.yml に残す = 過渡期運用ポリシー
として残しておく)。

## 解説まとめ

- **なぜ severity: warn か (= 運用 SLO の宣言)**:
  - **データ品質は二値ではない**: 「正しい / 壊れている」 の 2 値ではなく、
    「絶対 NG / 直すべき / 注意したい / 情報として知りたい」 と **重大度の
    スペクトル** がある。
  - **severity を test 単位で宣言** すると、その重大度が **manifest 上に
    機械可読で残る**。BI ツール / 運用ダッシュボードから「現在 WARN 状態の
    test 一覧」 を引けるようになる (= **データ品質の SLO ボード**)。
  - **dbt のテストは「単体テスト」 ではなく「データ契約 + 運用 SLO」**。
    Topic ⑥ 全体の核心メッセージ。
- **警報疲れ (alert fatigue) の回避**:
  - 全 test を ERROR にすると、軽微な逸脱でも CI 赤 → エンジニアが「またか」と
    無視 → 本当に重要な ERROR も見逃される、という負のループ。
  - WARN を **「気付くが止めない」** バッファに使い、ERROR を **「絶対止める」** に
    限定することで、ERROR の発火率を低く保つ → 発火時の信頼度を高く維持。
- **`error_if` / `warn_if` の発展系**:
  ```yaml
  - accepted_values:
      arguments:
        values: ['food', 'electronics', 'clothing', 'home', 'sports']
      config:
        severity: error
        warn_if: '>0'      # 1 件以上で WARN
        error_if: '>10'    # 11 件以上で ERROR
  ```
  「少しの逸脱は気付くだけ、大量逸脱は止める」 という閾値ベース運用が宣言できる。
- **CI exit code と GitHub Actions の挙動**:
  - WARN (exit 0) → workflow ジョブは緑、Annotations セクションに警告は残る
  - ERROR (exit 1) → workflow ジョブは赤、PR がブロックされる
  - severity 宣言は **PR ブロック条件をデータ契約レベルで宣言** している。
- **本問のロールバックを「あえて宣言は残す」 理由**:
  違反データを戻しても、`severity: warn` の宣言を schema.yml に残す。理由は
  「将来また category の過渡的逸脱があった時に、CI を止めずに気付ける」 ため。
  test 設定は **「今のデータ状態」 ではなく「契約と運用ポリシー」** を宣言する
  ものなので、データ修正と test 設定変更は別の判断軸で行う。
