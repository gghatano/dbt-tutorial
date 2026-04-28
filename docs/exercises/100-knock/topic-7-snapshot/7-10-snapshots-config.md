# 7-10: dbt_project.yml の snapshots: で運用ポリシーをプロジェクト既定化

## シナリオ

7-1 で書いた snapshot ファイルでは、`{{ config(...) }}` ブロックに
`target_schema='snapshots'` / `strategy='check'` / `unique_key='product_id'` /
`check_cols=['unit_price']` を **個別ファイルごと** に書いていた。

`target_schema` や `strategy` のような **運用ポリシー**は、プロジェクト全体の
規約にすべき性質のもの (= 「うちの snapshot は全部 `snapshots` schema に
作る」「`check` strategy を既定にする」)。これを各ファイルに書くと、
新しい snapshot を追加するたびに同じ宣言を写経することになり、規約から
ズレるリスクも上がる。

dbt は `dbt_project.yml` の `snapshots:` セクションで snapshot 設定の
**プロジェクト既定** を宣言できる。これによって個別ファイルからは
重複が消え、設定変更も 1 箇所で済む。models の `+materialized: view` と
同じ思想。

## 学べること

- `dbt_project.yml` の `snapshots:` セクションの書き方
- `+target_schema` / `+strategy` を **プロジェクト既定** にする宣言
- ポリシーは集約 / 個別差分は局所化、という設定の階層化原則
- 「**ロールバック可能な編集**」 の習慣 (本問は最後にロールバックする)

## 前提

- 7-1 完了 (`dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql` が存在)
- 7-9 まで完了 (snap が冪等 = この問の前後で行数が変わらない)
- `dbt parse` が通る

## 入力データ

不要。`dbt_project.yml` を編集するだけ。

## 課題

### Step 1: 現状の dbt_project.yml を確認

```bash
cat dbt/dbt_project.yml
```

`snapshots:` セクションは現状 **存在しない** (= snapshot 既定が無い → 個別
ファイルがすべて担っている状態)。

### Step 2: snapshots: セクションを追加

`dbt/dbt_project.yml` の末尾 (`models:` ブロックの下) に追記:

```yaml
snapshots:
  local_analytics:
    +target_schema: snapshots
    +strategy: check
```

意味:

- `local_analytics` (= プロジェクト名) 配下のすべての snapshot に対して
  `target_schema=snapshots` を既定とする
- 戦略は `check` を既定とする (= source 側の特定列の変化で履歴化)
- `unique_key` / `check_cols` は snapshot ごとに違うので個別ファイルに残す
  (= プロジェクト既定にしない)

### Step 3: 個別 snapshot ファイルから target_schema / strategy を **削除**

`dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql` の
`{{ config(...) }}` から `target_schema='snapshots'` と `strategy='check'`
の行を削除し、`unique_key` と `check_cols` だけ残す:

```sql
{% snapshot snap_products_100knock %}

{{
    config(
        unique_key='product_id',
        check_cols=['unit_price'],
    )
}}

select ...
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

### Step 4: parse → snapshot で動くことを確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
cd ..
```

期待:

- `dbt parse` 成功 (= snapshots: セクションが正しく認識される)
- `dbt snapshot` で `OK snapshotted snapshots.snap_products_100knock`
  が出る (= target_schema 規定値が効いて `snapshots` schema に作られる)
- 既に v1+v2 履歴があるので 2 回目相当 = `SELECT 0` (no-op)

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-7-snapshot/7-10-snapshots-config.grading.yaml
```

### Step 6: ロールバック (任意、後続の問への影響回避)

本問は **dbt_project.yml の編集** が成果物。後続演習で意図せぬ影響が出る
ようなら以下でロールバック:

```bash
git diff dbt/dbt_project.yml
git checkout -- dbt/dbt_project.yml
git checkout -- dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql
```

## 完了条件

- [ ] `dbt/dbt_project.yml` に `snapshots:` セクションが存在
- [ ] そのセクションに `+target_schema: snapshots` と `+strategy: check` がある
- [ ] 個別 snapshot ファイル (`snap_products_100knock.sql`) の config から
      `target_schema` / `strategy` が削除されている (= 重複が消えた)
- [ ] `dbt parse` 成功
- [ ] `dbt snapshot --select snap_products_100knock` 成功 (= 既定値が効いて動く)

## ヒント (詰まったら)

- **`+` を忘れる**: dbt の `dbt_project.yml` では config キーに `+` プレフィックス
  が必要 (`target_schema:` ではなく `+target_schema:`)。これがないと dbt は
  パスセグメントとして解釈してしまい意図しない挙動になる。
- **個別ファイル側を消し忘れる**: 個別 config が残っていても **個別が優先**
  されるので壊れはしないが、本問の主旨 (重複排除) からズレる。grading は
  「dbt_project.yml に宣言があり、parse が通る」 を主に見るので個別残しでも
  通る可能性はあるが、必ず削除すること。
- **`snapshots` schema が存在しない**: 7-1 Step 0 で作っているはず
  (`CREATE SCHEMA snapshots AUTHORIZATION dbt_user`)。無いと dbt が
  「schema 不在」 で ERROR を出す。
- **`strategy: check` が `check_cols` を要求**: `+strategy: check` だけでは
  各 snapshot が `check_cols` を持たないと parse エラーになる。`check_cols`
  は snapshot ごとに違うので **プロジェクト既定にせず**、個別ファイルに残す。
- **`models:` ブロックとインデントを揃える**: YAML はインデントセンシティブ。
  `snapshots:` は `models:` と同じ階層 (root 直下)。

## 解答例

詳細は [`7-10-snapshots-config.solution.md`](7-10-snapshots-config.solution.md) を参照。
