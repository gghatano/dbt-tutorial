# Topic ⑦ 履歴管理 (snapshot)

> **テーマ**: source の物理テーブルは「今この瞬間の事実」しか持たない。dbt snapshot は「この source は時間軸でどう同一性を保つか」を宣言する仕組み。SCD Type-2 として `dbt_valid_from` / `dbt_valid_to` を機械的に生成する。

## このトピックで学ぶこと

- `{% snapshot %}` ブロック、`check` / `timestamp` strategy
- `unique_key`, `check_cols`, `target_schema` の役割
- SCD Type-2 の挙動 (履歴行追加、`dbt_valid_to` の管理)
- `hard_deletes: new_record` (1.9+) で削除も履歴に残す
- snapshot 自身に schema test (`not_null: dbt_scd_id` 等)
- **point-in-time クエリ** ( `dbt_valid_from <= as_of < coalesce(dbt_valid_to, '9999-12-31')` )
- snapshot を `ref()` 経由で intermediate / mart に組み込む
- `dbt build` で一気通貫 (snapshot → ref → test)
- snapshot の冪等性 (no-op 挙動)
- `dbt_project.yml` の `snapshots:` セクションで運用ポリシー宣言

## 前提

- Topic ② ③ ④ 完了 (`raw_100knock` source、`int_*_100knock` 系が存在)
- 学習者は事前に `CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;` を実行 (Step 0)
- 学習者の snapshot は `dbt/snapshots/100-knock/topic-7/` に置く
- snapshot 命名: `snap_<name>_100knock`

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 7-1 | snap_products を check strategy で書く | 時間軸の同一性ルール |
| 7-2 | v2 を流し込んで履歴 v1+v2 を確認 | SCD Type-2 の挙動 |
| 7-3 | timestamp strategy を別 snapshot で | strategy の選択軸 |
| 7-4 | hard_deletes (1.9+) で削除も履歴 | 物理削除イベントの宣言 |
| 7-5 | snapshot の schema test | machine-generated でも明示契約 |
| 7-6 | point-in-time クエリ | snapshot の本質的価値 |
| 7-7 | snap を ref する int で「注文時点の価格」 | snapshot を DAG に組み込む |
| 7-8 | dbt build --select +int で一気通貫 | snapshot を含む build 順序 |
| 7-9 | snapshot 2 回叩いて no-op | 冪等性 |
| 7-10 | dbt_project.yml snapshots: 設定 | 運用ポリシー宣言 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-7-1-snap-products-check
```

CI: ブランチ名に `exercise-100-knock-7-N-...` を含めて push。

## 注意

- 7-1 Step 0 で snapshots schema を Postgres 上に手動作成
- 7-4 は dbt 1.9+ 機能 (本リポジトリ dbt-core 1.11 で動く想定だが、動かなければヒントレベル)
- 7-10 は dbt_project.yml 編集 (Step 5 ロールバック)
