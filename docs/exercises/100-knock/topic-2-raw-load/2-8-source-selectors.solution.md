# 2-8 解答例

## 実行コマンド

```bash
cd dbt
../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.*' --resource-type source > ../dbt/output_lineage.txt
cat ../dbt/output_lineage.txt
```

期待出力 (Topic ② 完了時点、staging 未着手の場合):

```
source:local_analytics.raw.customers
source:local_analytics.raw.products
source:local_analytics.raw.stores
source:local_analytics.raw.orders
```

`source:<project>.<source_name>.<table>` の表記。**4 行** が出れば本問は OK。

## 別パターン: `+` 演算子で下流を辿る

Topic ③ の staging を作ったあとに叩くと差が見える。

```bash
# customers source とその下流を全部列挙
cd dbt && ../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.customers+'
# source:local_analytics.raw.customers
# model:local_analytics.stg_customers          (Topic ③ で作る)
# model:local_analytics.mart_customer_kpis     (Topic ⑥ で作る)

# orders を起点に下流を全部
cd dbt && ../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.orders+'
```

これが「**この raw を変えたら何が壊れるか**」を 1 コマンドで答える方法。CI で "raw を触る PR" の影響範囲をコメントするのに使える。

## 別パターン: `--resource-type` の使い分け

```bash
# source だけに絞る
dbt ls --select 'source:raw.*' --resource-type source

# source の下流の model だけに絞る
dbt ls --select 'source:raw.orders+' --resource-type model

# test だけに絞る (source に張った not_null / unique が出る)
dbt ls --select 'source:raw.customers+' --resource-type test
```

実務だと「変更された raw の下流 test だけ実行」みたいな絞り込みに使う:

```bash
dbt test --select 'source:raw.customers+' --profiles-dir .
```

## 別パターン: `state:` と組み合わせる (発展)

```bash
# 前回 build 時点の manifest と比較して、変更された source の下流だけ build
dbt build --select 'source:state:modified+' --state ./previous_state --profiles-dir .
```

これが Slim CI の typical pattern。本問の範囲外だが、selector を覚えるとこの世界に入っていける。

## ファイル成果物

```bash
$ wc -l dbt/output_lineage.txt
       4 dbt/output_lineage.txt

$ cat dbt/output_lineage.txt
source:local_analytics.raw.customers
source:local_analytics.raw.products
source:local_analytics.raw.stores
source:local_analytics.raw.orders
```

(2-7 で `raw_alt` も追加済みなら、別途 `--select 'source:raw_alt.*'` で叩くと 4 行追加で出る)

## 解説まとめ

- **selector 言語は dbt の中核**: dbt の真の生産性は SQL ではなく **DAG をクエリできる selector** にある。`+`, `@`, `*`, `tag:`, `path:`, `state:` といった演算子を組み合わせると、何千 model のプロジェクトでも「この変更で再 build すべき範囲」をピンポイントで指定できる。本問はその入口。
- **`+` (graph operator) のメンタルモデル**: 矢印の向きで覚える。DAG は raw → staging → mart と流れるので、`source:raw.foo+` は「右に流れる先」= 下流。`+model:mart_foo` は「左から来る源」= 上流。両側 `+model:foo+` で「祖先と子孫を全部」。
- **CI での使い方**:
  - **影響範囲レポート**: PR で変更されたファイルから `source:...+` で下流 test を絞って実行 → CI 時間を短縮
  - **Slim CI**: `state:modified+` と `--state` を組み合わせて差分 build
  - **owner 別 build**: `tag:owner:team_a` で特定チームの model だけ build
- **出力をファイルに残す意義**: PR コメントや review メモに「この変更で影響を受けるノード」を貼り付けられる。`> output.txt` で残しておけば、後から「前回はこの 4 ノードが影響範囲だった」が辿れる。
- **`--resource-type` を覚える価値**: 一覧出力が長くなるプロジェクトでは絞り込みが必須。`source` / `model` / `test` / `snapshot` / `seed` / `analysis` / `exposure` / `metric` のいずれかを指定できる。
- **後続トピックへの伏線**: Topic ⑥ (exposures) で `+exposure:my_dashboard` を使うと「dashboard 起点で必要な model 全部」を build できるようになる。本問の `source:` 起点と同じ思想。
