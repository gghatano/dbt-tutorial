# 7-10 解答例

## ゴール再掲

- `dbt_project.yml` に `snapshots:` セクションを追加し、
  `+target_schema: snapshots` / `+strategy: check` をプロジェクト既定にする
- 個別 snapshot ファイルからは `target_schema` / `strategy` を削除
- `dbt parse` & `dbt snapshot` が成功する状態を残す

## 修正後 dbt/dbt_project.yml

```yaml
name: 'local_analytics'
version: '1.0.0'
config-version: 2

profile: 'local_analytics'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  local_analytics:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts

snapshots:
  local_analytics:
    +target_schema: snapshots
    +strategy: check
```

**ポイント**:

- **`snapshots:` は root 直下** (= `models:` と同階層)。インデントは 0 段。
- **`local_analytics:` でプロジェクト名で囲む**: dbt の慣習で「`<package_name>`
  配下の全 snapshot に適用」 という意味。これを省いて `+target_schema:` を直に
  書いてもこの project は単一パッケージなので動くが、明示する方が他パッケージ
  追加時に安全。
- **`+` プレフィックス**: dbt の `dbt_project.yml` 上の config キーは必ず
  `+` 付き。`target_schema:` (= 子セグメント) と区別するための文法。
- **`unique_key` / `check_cols` は project に書かない**: snapshot ごとに
  対象列が違う = 個別ファイルに残すべき。プロジェクト既定にすると間違った
  キーで履歴化される事故リスクが高い。

## 修正後 dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql

```sql
{% snapshot snap_products_100knock %}

{{
    config(
        unique_key='product_id',
        check_cols=['unit_price'],
    )
}}

select
    product_id,
    product_name,
    category,
    unit_price
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

**ポイント**:

- `target_schema='snapshots'` と `strategy='check'` の **2 行を削除**。
  プロジェクト既定で同じ値が効くので動作変わらず、重複だけ消える。
- `unique_key` と `check_cols` は **個別ファイルに残す** = snapshot ごとに
  違う設定だから。これが「ポリシーは集約 / 個別差分は局所化」の応用例。

## 動作確認

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
06:00:00  Found N models, M snapshots, ...
# parse 成功 = snapshots: セクションが正しく解釈された

$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
06:00:01  1 of 1 START snapshot snapshots.snap_products_100knock .............. [RUN]
06:00:01  1 of 1 OK   snapshotted snapshots.snap_products_100knock ........... [SELECT 0 in 0.18s]
06:00:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
# OK snapshotted snapshots.snap_products_100knock = target_schema が効いている

$ docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
120
# 7-9 までと同じ行数 = no-op で副作用なし
```

## ロールバック手順 (Step 6)

```bash
# 確認
$ git diff dbt/dbt_project.yml
+snapshots:
+  local_analytics:
+    +target_schema: snapshots
+    +strategy: check

$ git diff dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql
-        target_schema='snapshots',
-        strategy='check',

# ロールバック (採点後、後続演習に影響を出したくない場合)
$ git checkout -- dbt/dbt_project.yml \
    dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql
```

ロールバックは任意。本問の学習目的は「**集約 vs 局所** の判断軸を体感する」
ことなので、commit 前にロールバックしてもしなくても問題ない (採点はその時点
の HEAD の状態を見る)。

## 解説まとめ

1. **設定の階層化原則**: 「ポリシーは集約 (= プロジェクト既定)、固有値は
   局所化 (= 個別ファイル)」。`+target_schema` はチーム規約 = 集約、
   `unique_key` は snapshot 固有 = 局所化。models 側の
   `+materialized: view` も同じ思想。
2. **dbt_project.yml の `snapshots:` は宣言のハブ**: 新しい snapshot を
   追加した時、ここに既定があれば「target_schema どこにする?」を考えなくて
   良い = 規約逸脱のリスクが減る。これが「**設定をコードで宣言**」 の効能。
3. **`+` プレフィックスは config 注入のシグナル**: YAML 上で「これは config
   値」 と「これは子セグメント」 を区別する文法。`+materialized:` /
   `+schema:` / `+target_schema:` / `+strategy:` などすべて共通。
4. **個別ファイルに残すべき設定の見分け方**: 「snapshot ごとに値が変わる
   もの」 は残す (= `unique_key`, `check_cols`)。「全 snapshot で同じに
   しておきたい運用ポリシー」 はプロジェクト既定 (= `target_schema`,
   `strategy`)。判断軸を持つと迷いが減る。
5. **ロールバック可能な編集**: 設定変更系 (= 影響範囲がプロジェクト全体に
   及ぶ) は、Step 6 のロールバック手順をペアで持っておくと PR レビューや
   実験がしやすくなる。「**この変更を後で取り消すには**」 を最初から
   設計に入れる習慣 = SRE 的な良い習慣。
6. **Topic ⑦ の総括**: 7-1〜7-10 で「snapshot を作る → 履歴を引く →
   model に組み込む → 一気通貫で動かす → 冪等性確認 → プロジェクト規約化」
   と進んだ。これで snapshot は「孤立した別オペ」ではなく、 dbt DAG の
   1 つのノード型として運用できる状態になる。
