# 2-8: `dbt ls --select source:raw.*` / `source:raw.customers+` で source とその下流を列挙

## シナリオ

「この raw を変えたら何が壊れるか？」は data engineer が日常的に答えるべき問い。dbt は manifest 上の DAG をクエリできる **selector 言語** を持っており、`source:raw.*` で source ノードを起点に、`+` 演算子で下流を辿れる。本問では `dbt ls` を 2 通り叩いて、出力をテキストに保存する。これは「DAG 上で影響範囲を機械的に列挙する」という運用スキルの最小単位。

CI 上では「PR で変更された raw に対して `+` 下流を `dbt build --select` で再ビルドする」という形で日常的に使う。今回はその素振りとして、selector の構文を体に染み込ませる。

## 学べること

- `dbt ls --select source:<source_name>.<table>` の基本形
- `*` ワイルドカードで「ある source 配下の全 table」を列挙
- `+` (graph operator) で「その node の下流」を含めて列挙
- selector の出力をファイルにリダイレクトして CI 成果物として残す習慣
- 「壊したらどこに波及するか」を 1 コマンドで答えられる開発フロー

## 前提

- 2-2 で `dbt/models/100-knock/topic-2/sources.yml` (`name: raw`) が宣言済み
- (理想的には) Topic ③ の staging が 1 つでもあると `+` 下流が見えて学習効果が上がる。staging が 0 でも本問の採点は通る (source 自身 4 件が出るため)。
- `cd dbt && dbt parse --profiles-dir .` が通る状態

## 入力データ

不要 (本問は selector の素振り + 出力保存だけ)。

## 課題

### Step 1: source 全件を列挙して保存

```bash
cd dbt
../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.*' --resource-type source > ../dbt/output_lineage.txt
cat ../dbt/output_lineage.txt
# source:local_analytics.raw.customers
# source:local_analytics.raw.products
# source:local_analytics.raw.stores
# source:local_analytics.raw.orders
```

要件:

- 出力ファイル: `dbt/output_lineage.txt`
- 1 行 1 ノード形式 (デフォルトの `dbt ls` 出力)
- **少なくとも 4 行** (= 4 source を列挙できている)
- staging があれば `+` 演算子で増えるが、最低 4 件の source ノードが書かれていれば OK

### Step 2: customers の下流まで含めて確認 (採点 check の一部)

```bash
cd dbt
../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.customers+'
# source:local_analytics.raw.customers
# (もし stg_customers があれば) model.local_analytics.stg_customers
# (mart まであれば) model.local_analytics.mart_customer_kpis
```

`+` 演算子は「**その node とその下流**」を返す。staging を作っていない段階では source 1 件のみ。Topic ③ 完了後にもう 1 度叩くと意味が出てくる。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-8-source-selectors.grading.yaml
```

## 完了条件

- [ ] `dbt/output_lineage.txt` が存在する
- [ ] その中に少なくとも `raw.customers` / `raw.products` / `raw.stores` / `raw.orders` の 4 source が書かれている (4 行以上)
- [ ] grader 内で `dbt ls --select 'source:raw.*'` を再実行しても 4 行以上が返る (= 宣言が正しく manifest に乗っている)
- [ ] grader 内で `dbt ls --select 'source:raw.customers+'` が exit 0 で返る (selector 構文として有効)

## ヒント (詰まったら)

- **`--resource-type source`**: `dbt ls` のデフォルト出力には model も snapshot も混ざる。`--resource-type source` で source だけに絞れる。本問の採点は「4 行以上」なので絞らなくても通るが、出力を読みやすくする実務的なコツ。
- **`+` の左右の意味**: `model:foo+` は foo **以降** (子孫)、`+model:foo` は foo **以前** (祖先)。`source:` は基本的に「ソース→下流」しか向きがないので `source:raw.customers+` の **右側** の `+` を使う。
- **ワイルドカード**: `source:raw.*` の `*` は「raw 配下の全 table」を意味する。`source:*.customers` のようにテーブル名側にもワイルドカードを書ける。
- **出力先**: `dbt/output_lineage.txt` のように `dbt/` 配下に置けば、worktree 切り替えで失われない。`/tmp/` 配下に書くと CI 成果物としてアーカイブできない。
- **`--profiles-dir .`**: dbt のサブディレクトリで叩く前提なので必ず必要。忘れると `~/.dbt/profiles.yml` を見にいって落ちる。

## 解答例

詳細は [`2-8-source-selectors.solution.md`](2-8-source-selectors.solution.md) を参照。
