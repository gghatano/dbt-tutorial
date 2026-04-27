# Junior Engineer Review — 2026-04-26

## 想定読者

- バックエンド経験 1〜2 年
- SQL は SELECT/JOIN/集約は書ける、ウィンドウ関数や CTE はあやふや
- dbt は名前を知っている程度、触ったことなし
- Docker は `docker run` / `docker compose up` レベル、ネットワーク・ボリュームの理解は浅い
- Terraform / IaC は未経験
- macOS（Apple Silicon）で作業する想定。Colima / uv / brew は知らないかも
- データ基盤（ELT/ETL、DWH、データマート）の概念は曖昧

## サマリ

- **総評**: 「動かす」ための材料は揃っており、コミット履歴・ADR・spec・練習問題まで一気通貫で揃った教材として完成度が高い。一方でジュニア視点では、(1) **「最初の `dbt run`」までの暗黙の前提が多い**（uv のインストール・`set -a; source .env` の意味・cwd 切替・schema 解決マクロの存在意義など）、(2) **「なぜ dbt なのか」「なぜ raw/staging/intermediate/marts なのか」「なぜ readonly_user なのか」といった概念面の "WHY" が ADR に閉じ込められておりトップ動線から触れにくい**、(3) **`spec2.md` や ADR の欠番（0003 / 0007）など旧版残置が読み手を混乱させる**、という 3 系統の伸びしろがある。各ファイル単体の品質は高いので、トップページ（README）に概念ガイドへの導線を 1 本通し、暗黙の前提を明示するだけで体験は大幅に改善する。
- Critical: 6 件
- Major: 12 件
- Minor: 9 件
- **良かった点**: ADR が判断ログとして十分に機能している／dbt_user と readonly_user の責務分離が綺麗／scripts のモジュール docstring が丁寧／生成データが固定 seed で冪等／smoke_test.py の strict / warn 分離思想が明文化されている／練習問題の難易度勾配が考えられている。

---

## 評価詳細

### 1. オンボーディング

#### 🔴 [C-01] uv のインストール手順が「URL 参照」で済まされ、初学者の最初のブロッカになる

- 場所: `README.md` L65-68
- 問題: `# uv は https://docs.astral.sh/uv/getting-started/installation/ 参照` とリンクだけ。Apple Silicon の brew 利用者は `brew install uv` で済むが、それさえ書かれていない。続く `uv venv --python 3.12` でいきなり 3.12 を取りに行くため、**Python 3.12 を別途入れる必要がない**ことも明示されていない。ジュニアは「pyenv で 3.12 を入れる」など余計な作業に走りがち。
- 影響: phase-03 に入る前にここで詰まる。CLI が見つからない／PATH 追加が必要／Python が既存の 3.9 でフォールバックされる、などの落とし穴が連鎖する。
- 提案: クイックスタート §1 を以下に置換 ——
  ```bash
  # 1. ツール（macOS / Homebrew 前提）
  brew install colima docker docker-compose uv
  brew install hashicorp/tap/terraform

  # uv は Python 自体も管理する。3.12 が手元になくても
  # `uv venv --python 3.12` が必要なバージョンを自動 DL する。
  # システム python3 / pyenv は不要。
  ```
  さらに「これらが何のためのツールか」を 1 行ずつ括弧で添える（colima=macOS 用 Linux VM、uv=Python パッケージマネージャ、Terraform=IaC、等）。

#### 🔴 [C-02] `set -a; source .env; set +a` が説明なしで登場し、何をしているかわからない

- 場所: `README.md` L101、`docs/exercises/README.md` L37、`docs/exercises/01-ingest-reviews.md` L108 ほか頻出
- 問題: シェル経験が浅い読者は `set -a` / `set +a` の意味を知らない。`profiles.yml` が `env_var('DB_HOST', 'localhost')` を読むため、シェルに env を流し込まないと dbt が `localhost` フォールバック（or 失敗）する。ところがその因果関係が README にも `profiles.yml` にも書かれていない。
- 影響: 「dbt debug が password authentication failed と言うのに `.env` には正しい値が書いてある」という症状で延々ハマる。
- 提案: README §6 直後に以下のコラムを追加 ——
  ```markdown
  > **`.env` を dbt に渡す仕組み**
  >
  > `dbt/profiles.yml` は `{{ env_var('DB_HOST', ...) }}` で **シェル環境変数** を読む。
  > `.env` ファイルそのものは dbt には見えないので、dbt を呼ぶ前にシェルへ流し込む必要がある。
  >
  > ```bash
  > set -a            # この後に export 相当の挙動を有効化
  > source .env       # KEY=VALUE を読み込み
  > set +a            # 元に戻す
  > ```
  >
  > Python スクリプト（`scripts/*.py`）は `python-dotenv` 経由で `.env` を直接読むので
  > この手順は不要。違いを意識すると詰まりにくい。
  ```

#### 🔴 [C-03] cwd（カレントディレクトリ）の前提がコマンドごとに変わるが、明示されていない

- 場所: `README.md` L77-107、`docs/exercises/*` 各ファイル
- 問題: README は「`cd infra/terraform`」「`cd ../../`」「`cd dbt`」「`../.venv/bin/dbt ...`」を混在させているが、cwd を「いまどこにいるか」を明示する `$ pwd` 例や視覚的 marker が無い。Exercise でも `cd ..` `cd dbt` が散発する。
- 影響: ジュニアは「`.venv/bin/python` か `../.venv/bin/python` か」「`source .env` か `source ../.env` か」を迷い続ける。実際 ADR-0009 §5 も `set -a; source ../.env; set +a` と書いており、README とずれている。
- 提案: クイックスタートの先頭に以下を追加し、各 step の冒頭にプロンプト風の cwd を書く ——
  ```markdown
  > **cwd 規約**
  >
  > すべてのコマンドは「コードブロック直前にどこから実行するか」を明示する。
  > `~/repo` をリポジトリルートとし、コードブロック内の `$ ` プロンプトは
  > 末尾の `cwd:` コメントで現在地を示す。
  >
  >     # cwd: ~/repo
  >     docker compose up -d
  >
  >     # cwd: ~/repo/dbt
  >     ../.venv/bin/dbt run --profiles-dir .
  ```

#### 🟡 [M-01] `~/.docker/config.json` の `credsStore` 削除がトラブルシュートに埋もれている

- 場所: `README.md` L166-169、`ADR-0002`
- 問題: Docker Desktop からの移行ユーザでは「最初に `docker compose up` するとハングする」のがほぼ初手で起きる。これは前提セクションに書くべき内容。Troubleshooting に置くと「ハマってから掘り出す」順序になる。
- 提案: 「前提」セクション L60 に注意事項として以下を移動・展開 ——
  ```markdown
  > **Docker Desktop からの移行者向け**: `~/.docker/config.json` に
  > `"credsStore": "desktop"` が残っていると `docker pull` がハングする
  > （ADR-0002）。事前に該当行を削除（バックアップ推奨）。
  > 確認コマンド: `grep credsStore ~/.docker/config.json || echo "OK"`
  ```

#### 🟡 [M-02] Colima が起動済みかどうかの確認手順が無い

- 場所: `README.md` L70-74
- 問題: `colima start --cpu 4 --memory 8 --disk 20` が「すでに起動中なら何が起きるか」「以前に弱いリソースで起動していたらどう増やすか」が書かれていない。Metabase 起動時にメモリ不足で落ちる経路がある（dashboard.md にだけ記載）。
- 提案: §2 を ——
  ```bash
  # 既存 VM があるなら停止してから再起動（リソース変更のため）
  colima status >/dev/null 2>&1 && colima stop
  colima start --cpu 4 --memory 8 --disk 20
  colima status   # arch / runtime / cpu / memory が表示されること
  ```
  に差し替え、「Metabase まで動かしたい人は memory 8 GB 必須」を明記。

#### 🟡 [M-03] Terraform 用の Postgres 接続情報がどこから来るか不透明

- 場所: `README.md` L77-81、`infra/terraform/variables.tf` L19-30
- 問題: `terraform apply -auto-approve` が `analytics_user / analytics_password` で接続するのは `variables.tf` の default 値があるから、という事実が README に書かれていない。`.env` を変更したら `terraform apply` が通らない可能性をジュニアは予想できない。
- 提案: §4 の直前に「Terraform は `infra/terraform/variables.tf` の default を superuser 接続に使う。`.env` の値を変えた場合は `-var` か `terraform.tfvars` で同じ値を渡す必要がある」と一文追加。

#### 🟢 [m-01] `.env` 作成手順がヒアドキュメントなのでコピペ事故が起きやすい

- 場所: `README.md` L88-94
- 提案: `.env.example` をコピーする方が安全 ——
  ```bash
  cp .env.example .env
  # 必要なら METABASE_ADMIN_PASSWORD / METABASE_DB_RO_PASSWORD を埋める
  ```
  現状の README §6 のヒアドキュメントは Metabase 用の `METABASE_*` を含まないので、§7 (Metabase) で .env を上書きする破目になる。

---

### 2. 概念の説明

#### 🔴 [C-04] 「raw / staging / intermediate / marts って何？なぜ分ける？」が概念として説明されていない

- 場所: `docs/spec.md` §4、`README.md` L29-40
- 問題: spec §4 の表は「役割」を 1 行で済ませている。ジュニアは「raw を直接 BI に出せばいいじゃん」「staging は単に view ですよね？」というレベルで止まる。dbt 公式の "Medallion architecture" や責務分離（型統一・テストの局所化・再計算コスト・依存最小化）の文脈が無い。
- 影響: 「コピペで動いた」で終わる。練習問題の Exercise 02 で intermediate と mart を分ける意味も腹落ちしない。
- 提案: `docs/concepts.md` を新設（または README の「アーキテクチャ」直下にサブセクション）し、以下を書く ——
  - 各層の **「やってよいこと／やってはいけないこと」** マトリクス
  - 「型変換は staging まで、ビジネスロジックは intermediate、KPI 集計は marts」の境界線
  - 「raw を BI に直接見せない」3 つの理由（型がブレる／PII が混じる／責任所在が不明）
  - 公式 dbt docs `docs.getdbt.com/best-practices/how-we-structure/1-guide-overview` への外部リンク

#### 🔴 [C-05] 「dbt とは」「なぜ dbt」が一切書かれていない

- 場所: `README.md`、`docs/spec.md`
- 問題: 採用技術表に「dbt-core 1.11.8」とあるだけで、SQL の transform を git 管理する／DAG／テストフレームワーク／docs 自動生成、という存在意義が説明されない。dbt 未経験のジュニアは README を読んでも「PostgreSQL に SQL を流すだけのツール」という解像度のまま進む。
- 提案: README 「採用技術」の前に短い概念節を入れる ——
  ```markdown
  ## このプロジェクトで触れるコア概念

  - **dbt (data build tool)**: 「SELECT 文を書くだけで」テーブル / view を
    宣言的に管理できるツール。`ref()` で依存関係を解決して DAG を構築し、
    テスト・ドキュメント・モデル間の lineage を一括で扱える。Python の
    Airflow が「ジョブ実行の DAG」だとすれば、dbt は「SQL transform の DAG」。
  - **IaC (Infrastructure as Code)**: 環境（schema / role / grant）を
    コードで宣言し、再現可能にする手法。本プロジェクトでは Terraform 1.14 を採用。
  - **ELT (Extract → Load → Transform)**: 旧来の ETL と違い、生データを先に
    DWH へ流し（Extract → Load）、SQL で変換する（Transform）スタイル。
    dbt は ELT の T 担当。
  ```

#### 🟡 [M-04] `generate_schema_name` macro の override が「やや高度な dbt の話」のまま

- 場所: `dbt/macros/get_custom_schema.sql`、`README.md` L171-174
- 問題: ADR-0005 で詳しく解説しているが、「デフォルト挙動だと `<target>_<schema>` という prefix 命名になる」を初学者は実感できない。Exercise 04 のヒントで突然 `target_schema='snapshots'` が登場する伏線にもなっており、このマクロを「外す」とどうなるかをコメント／ドキュメントで一度見せておく価値が高い。
- 提案: `get_custom_schema.sql` のコメントに「無効化した場合の挙動」を 1 例添える ——
  ```sql
  {#-
    ...（既存）

    Reference: this macro is what makes `+schema: marts` map directly to
    the Postgres schema `marts`. Without this override, the same config
    would produce `<target_schema>_marts` (e.g. `staging_marts`), which
    would not match the schemas created by Terraform.
    Try removing this file temporarily and run `dbt run`: dbt will
    create new schemas like `staging_marts`, `staging_intermediate` etc,
    which is the default dbt-postgres behaviour.
  -#}
  ```

#### 🟡 [M-05] `readonly_user` を分ける理由が dashboard.md にしかない

- 場所: `docs/dashboard.md` L122-135、`infra/terraform/main.tf` L80-107
- 問題: phase-02 の段階で `dbt_user` と `readonly_user` の 2 ロールを作るが、なぜ readonly_user が必要なのかは BI を立ち上げる段（dashboard.md）まで現れない。dashboard を立ち上げない学習者には永遠に意味不明のままになる。
- 提案: README の「採用技術」表の下、または ADR-0009 §3.2 を README にダイジェスト引用して以下を追加 ——
  ```markdown
  ## ロール分離 (dbt_user / readonly_user)

  - **dbt_user**: 4 schema (raw/staging/intermediate/marts) のオーナー。
    raw ロード〜dbt run まで担当。
  - **readonly_user**: `marts.*` の SELECT のみ。BI ツール (Metabase) や
    アナリストが触る想定。誤って DELETE / UPDATE が走っても拒否される保険。

  「dbt が書く側」「人間 / BI が読む側」の責務分離を最初から作っておくと、
  クラウド DWH に載せ替えるときも同じ思想が流用できる。
  ```

#### 🟡 [M-06] 「なぜ SCD Type-2」「なぜ snapshot」が Exercise 04 でいきなり登場する

- 場所: `docs/exercises/04-snapshot-product-price.md`
- 問題: 「価格が改定されると当時の価格が消える」の問題提起はあるが、SCD Type-1/2/3 の概念図や、なぜ Type-2（valid_from/valid_to を持つ行追加）が標準なのかには踏み込んでいない。`dbt_valid_to` が NULL = 現役、という符号化も初出。
- 提案: Exercise 04 冒頭に簡易図解（mermaid）を追加 ——
  ```mermaid
  gantt
      title Product 003 unit_price 履歴 (SCD Type-2)
      dateFormat  YYYY-MM-DD
      section v1 (1240円)
      valid_from 〜 valid_to : 2026-04-01, 2026-04-15
      section v2 (8520円)
      valid_from 〜 NULL    : 2026-04-15, 2026-12-31
  ```
  と「Type-1（上書き）/ Type-2（履歴行追加）/ Type-3（前回値列追加）」の 1 行比較。

#### 🟢 [m-02] view と table と incremental の違いが「使い分けの結論」だけになっている

- 場所: `dbt/dbt_project.yml`、ADR-0006
- 提案: README または concepts.md に以下の 1 表を追加 ——
  | materialization | 再計算 | 速度（参照） | ストレージ | 使い所 |
  |---|---|---|---|---|
  | view | 参照のたび | 遅い | ほぼ 0 | 軽い変換、staging |
  | table | dbt run のたび full | 速い | 行数分 | mart、頻繁に参照される集計 |
  | incremental | 差分のみ追加 | 速い | 行数分 | 大規模 fact、毎日追記 |
  | ephemeral | 物質化しない（CTE 化） | 中 | 0 | プライベート中間 SQL |

---

### 3. ドキュメント体系

#### 🔴 [C-06] `docs/spec2.md` が残置されており、`spec.md` との関係が読み取れない

- 場所: `docs/spec2.md`、`docs/decisions/0001-autonomous-development-setup.md` L18
- 問題: ADR-0001 §6 で「spec2 は履歴として残す」とは書かれているが、`docs/spec2.md` 自体には「これは spec.md に統合済みの旧版」という deprecation note が無い。ファイル冒頭は `以下を spec.md としてそのまま使えます。…` と ChatGPT 回答を貼り付けたままで、リポジトリの "正" 仕様と区別がつかない。コードブロック中の triple-backtick ネスト破綻（L71 の `````` と L322 の `````` ）も残っている。
- 影響: ジュニアが `spec2` を最新だと誤読する／README が `spec.md` のみリンクしていることに気づかず両方読んで矛盾に悩む。
- 提案: `docs/spec2.md` の冒頭に以下を追記（または rename して `archive/spec_initial_draft.md`）——
  ```markdown
  > **DEPRECATED**: 本ファイルは ChatGPT に最初に書いてもらった spec の素案。
  > 以降の更新は `docs/spec.md` に統合済み。リポジトリの正仕様は `spec.md`。
  > このファイルは履歴保全のためだけに残しています（ADR-0001 §6）。
  ```

#### 🟡 [M-07] ADR の番号が飛んでいる（0003 / 0007 が欠番）

- 場所: `docs/decisions/`
- 問題: 0001, 0002, 0004, 0005, 0006, 0008, 0009, 0010 と並ぶが 0003, 0007 が無い。README L156-162 のリンクも 0003/0007 を載せていないので「リンク切れ」ではないが、ADR の番号は通常 immutable で詰めない運用とはいえ、欠番の経緯がどこにも書かれていない。
- 提案: `docs/decisions/README.md`（新設）または ADR-0001 末尾に「0003 / 0007 は番号確保のみ予約済（PR 中で statu未着 になった案）」など 1 行のメモを残す。または欠番のまま `0001-autonomous-development-setup.md` に「番号 0003, 0007 は draft 中で superseded」と注記。

#### 🟡 [M-08] README §「ドキュメント」セクションが片道参照になっている

- 場所: `README.md` L144-162
- 問題: README → spec / ADR / exercises は貼られているが、`dashboard.md` への直接リンクが README から無い（「次フェーズ候補（spec §14）」で BI 言及はあるが文中リンクなし）。Metabase は 5d0ac03 で導入済なので、README から動線を張っておきたい。
- 提案: 「ドキュメント」セクションに `[docs/dashboard.md](docs/dashboard.md) — Metabase で marts を可視化する手順（自動 bootstrap 含む）` を追加。同時に `ADR-0010` も README に追加。

#### 🟡 [M-09] spec §3 のディレクトリ構成図が現状と乖離

- 場所: `docs/spec.md` L26-68
- 問題: spec §3 のツリーは `tests/` 配下に `assert_positive_sales_amount.sql` の 1 本しか書かれておらず、現存する 4 本（assert_positive_quantity / assert_marts_total_sales_non_negative / assert_daily_sales_not_empty）が反映されていない。`dbt/macros/`, `dbt/seeds/`, `dbt/snapshots/`, `scripts/exercises/`, `scripts/metabase_bootstrap.py`, `docs/exercises/`, `docs/dashboard.md` も漏れている。
- 提案: spec §3 を README §「ディレクトリ構成」と一致させて再生成。または spec §3 の冒頭で「これは初期計画。実装後の最新ツリーは README §ディレクトリ構成を参照」と免責する。

#### 🟢 [m-03] ADR-0009 の本文中に「最終ブランチ: feature-phase-06-task-003-completion」と書かれているが現ブランチは異なる

- 場所: `docs/decisions/0009-project-completion-summary.md` L25
- 問題: 現在のレビューは `feature-junior-review` ブランチで、main にマージされた後の状態。ADR は時点記録なのでこの記述は問題ないが、未経験者は「いま自分はどのブランチにいるべき？」を見失う。
- 提案: ADR-0009 の冒頭に「本 ADR 記録時のブランチ: ...（その後 main にマージ済み）」と明示。

#### 🟢 [m-04] `docs/tasks/README.md` のステータス語彙と各 task ファイルが一致していない可能性

- 場所: `docs/tasks/README.md` L7-10、各 `phase-NN/task-MMM.md`
- 提案: 全タスクを一読し、`Status: Done` のフォーマット一貫性を最後に検算。Done でないタスクは `Blocked` 等に移行する仕組み（TODO 化）。

---

### 4. コード品質と可読性

#### 🟡 [M-10] `dbt/profiles.yml` が `target.schema: staging` をマジック値にしている

- 場所: `dbt/profiles.yml` L11
- 問題: ADR-0005 で「`target.schema = staging` は custom macro と組み合わせる前提のフォールバック」と説明があるが、`profiles.yml` 本体にコメントが無い。読み手は「なぜ staging なのか」「これを変えると何が壊れるか」を判断できない。
- 提案: `profiles.yml` 上にコメントを追加 ——
  ```yaml
  # schema: macros/get_custom_schema.sql により `+schema:` 指定の付いた
  # モデルは custom_schema_name がそのまま採用される。ここで指定する
  # `schema: staging` は `+schema:` 未指定モデルのフォールバック先で、
  # MVP 内の全モデルは layer ごとに `+schema:` を持っているので
  # 実際にはこの fallback には到達しない。詳しくは ADR-0005。
        schema: staging
  ```

#### 🟡 [M-11] singular test が「失敗時に何を返すか」が SQL コメントだけにあり、ジュニアは「なぜ SELECT 文がテストになる？」が腹落ちしない

- 場所: `dbt/tests/assert_*.sql`
- 問題: dbt singular test は「行が返ったらテスト失敗」という挙動だが、初学者は「assert_positive_sales_amount.sql は単なる SELECT 文に見える」。SQL コメントには 1 行説明があるが、`docs/spec.md` §9 や README にはこの仕組みの解説が無い。
- 提案: README にテストの 2 系統（generic / singular）の概念図を入れる ——
  ```markdown
  ## dbt のテスト 2 種

  - **generic test** (schema.yml に YAML で書く):
    `not_null` / `unique` / `relationships` / `accepted_values` などの
    ビルトイン。複数列で再利用される定型チェック。
  - **singular test** (`tests/*.sql` に SQL を書く):
    「失敗行を返す SELECT 文」を書くだけ。1 行でも返ったら fail。
    `assert_positive_sales_amount.sql` は `WHERE sales_amount < 0` で
    違反行を返している。

  この 2 種を組み合わせて 61 件のテストを構成している（spec §9）。
  ```

#### 🟡 [M-12] `assert_marts_total_sales_non_negative.sql` の UNION ALL は工夫が見えるが、初学者には「3 mart を一気にチェックしている」工夫が伝わらない

- 場所: `dbt/tests/assert_marts_total_sales_non_negative.sql`
- 提案: 先頭コメントを拡張 ——
  ```sql
  -- 3 mart の total_sales_amount >= 0 を 1 つのテストで確認する。
  -- 別個の test ファイル 3 本にしてもよいが、UNION ALL で `mart` ラベル
  -- を持たせると「どの mart のどの行が落ちたか」が失敗時に判別できる。
  -- key_value 列に PK を text にしてキャストして詰めているのは、
  -- 3 mart の PK が text と date でズレているため。
  ```

#### 🟡 [M-13] `int_order_details.sql` の `INNER JOIN` の根拠コメントが ADR-0006 を参照しないと弱い

- 場所: `dbt/models/intermediate/int_order_details.sql` L4-5
- 提案: コメントに ADR への明示参照を入れる ——
  ```sql
  -- INNER JOIN: stg_orders FKs are validated by relationships tests in
  -- staging/schema.yml, so any orphan FK is caught upstream.
  -- See docs/decisions/0006-marts-modeling.md §1 for the trade-off
  -- (LEFT JOIN was rejected because it would silently mask FK breakage).
  ```

#### 🟢 [m-05] `mart_*.sql` のコメントが「materialized as table」を機械的に繰り返している

- 場所: `dbt/models/marts/mart_*.sql`
- 提案: 重複コメントを削り、各 mart 固有の意図（例: `mart_daily_sales` の `customer_count = COUNT(DISTINCT)` の意味）に置き換える。ADR-0006 §4 で説明している「customer_count と order_count を別 KPI として扱う」を SQL コメント側にも 1 行入れる。

#### 🟢 [m-06] `scripts/metabase_bootstrap.py` のモジュール docstring に環境変数一覧が無い

- 場所: `scripts/metabase_bootstrap.py` L1-16
- 提案: docstring 末尾に「Required env vars: METABASE_ADMIN_EMAIL / METABASE_ADMIN_PASSWORD / METABASE_DB_RO_PASSWORD」「Optional env vars: METABASE_URL (default http://localhost:3000), METABASE_SITE_LOCALE (default ja), ...」を追加。`.env.example` でも `METABASE_ADMIN_PASSWORD` がコメント `# password is set in .env (gitignored)` のみで、何を入れるか明示されていないので併せて修正。

---

### 5. トラブルシュート

#### 🟡 [M-14] エラーメッセージから対処を引く逆引きが無い

- 場所: `README.md` L164-187
- 問題: 既知の罠は 4 件（credsStore / schema prefix / Apple Silicon / Postgres 接続）あるが、実際にジュニアが目にする可能性のあるエラー文字列との対応表がない。例: `password authentication failed`、`could not connect to server`、`relation "raw.orders" does not exist`、`Compilation Error in macro generate_schema_name`、`Database Error: permission denied for schema marts`、Metabase の `Couldn't connect to the database` など。
- 提案: README §トラブルシュートに以下のような表を追加 ——
  | エラー文字列 (抜粋) | 起きる場面 | 一次切り分け | 詳細 |
  |---|---|---|---|
  | `password authentication failed for user "dbt_user"` | dbt run / smoke_test | `set -a; source .env; set +a` を忘れている可能性 | C-02, ADR-0008 §異常系 |
  | `could not connect to server: Connection refused` | dbt debug / psycopg | Postgres コンテナが落ちている／ポート競合 | M-02, README L181-187 |
  | `relation "raw.orders" does not exist` | dbt run | `load_raw_data.py` 未実行 | README §クイックスタート step 7 |
  | `permission denied for schema marts` | Metabase 接続 | readonly_user に grant が走っていない／terraform apply 不足 | dashboard.md M-05 |
  | `Couldn't connect to the database` (Metabase 設定画面) | Metabase setup | host を `localhost` にしている。`postgres` を使う | dashboard.md L74-78 |
  | `Compilation Error: ... generate_schema_name` | dbt run | macros/get_custom_schema.sql を消した | ADR-0005 |

#### 🟡 [M-15] Metabase がヘルシーになるまでの待ち時間に対する期待値が一箇所にない

- 場所: `docs/dashboard.md` L11-18
- 問題: `60〜120 秒`の数値はあるが、「途中状態の表示」「`docker logs local-data-metabase --tail 50` を回す目安」が無い。`scripts/metabase_bootstrap.py` の `wait_for_health` も 120 秒 timeout で、健全な状態でも初回は 90 秒ぐらいかかる。
- 提案: dashboard.md に「初回 60〜120 秒、2 回目以降 10〜30 秒」「`watch -n 5 'docker inspect ... Health.Status'` で進捗確認」を追加。

#### 🟢 [m-07] `psycopg` の `[binary]` extras が必須である理由が requirements.txt から読めない

- 場所: `requirements.txt` L3、ADR 群
- 問題: Apple Silicon 上で `psycopg[binary]` ではなく `psycopg` だと libpq の build 失敗が起こりがち。これは ADR-0008 で軽く触れているが requirements.txt にコメントが無い。
- 提案: requirements.txt はコメント不可なのでファイル冒頭に注記を追加するか、README §クイックスタートに「Apple Silicon で `psycopg` 単体を入れると build 失敗するので `psycopg[binary]` を必ず使う」を追加。

---

### 6. 練習問題（docs/exercises/）の教材性

#### 🟡 [M-16] Exercise 03 の Step 3 が「ほぼ解答」を本文に書いてしまっている

- 場所: `docs/exercises/03-incremental-orders.md` L73-98
- 問題: `stg_orders_inc.sql` の完成形 SQL がテキスト中に提示され、その下で「上は要件を全部見せてしまう（解答に近い）ので、まずは [...] 自力で書けるか試す」と注釈が入る。要件理解よりも先にコード全文を読んでしまう。
- 提案: Step 3 から完成形を削除し、要件箇条書きだけ残す。完成形は `solutions/03-*.solution.md` のみに置く ——
  ```markdown
  ### Step 3: `stg_orders_inc.sql` を incremental で実装

  `dbt/models/exercises/03/stg_orders_inc.sql` を作る。

  要件:
  - `materialized='incremental'` / `unique_key='order_id'`
  - `incremental_strategy='merge'`、`on_schema_change='fail'`
  - `is_incremental()` で 2 回目以降のみ
    `where loaded_at > (select max(loaded_at) from {{ this }})` を効かせる
  - 初回 / `--full-refresh` 時は全件 SELECT になることを確認

  詰まったら solutions/ を見る前に、まず以下のヒントを読む:
  ```

#### 🟡 [M-17] Exercise 04 の前提となる `snapshots` schema 作成が「ヒント」に隠れている

- 場所: `docs/exercises/04-snapshot-product-price.md` L117
- 問題: `CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user` を事前に流す必要があるが、これは Step 0 として明示すべき手順。ジュニアは Step 1 の `dbt snapshot` をいきなり叩いて「schema が無い」というエラーで止まる。
- 提案: 課題セクションの最初に Step 0 を新設 ——
  ```markdown
  ### Step 0: snapshots schema を用意する

  Terraform は raw/staging/intermediate/marts の 4 schema しか作っていない。
  snapshot を `snapshots` schema に置くために事前に手で作る。

      docker exec -i local-data-postgres psql -U analytics_user -d analytics \
          -c "CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;"

  本番運用なら Terraform に schema を追加するべきだが、本演習では学習目的で
  手動作成にとどめる。
  ```

#### 🟡 [M-18] Exercise 02 の「INNER vs LEFT」を学習者に決めさせるが、判断のチェックリストが薄い

- 場所: `docs/exercises/02-mart-product-rating.md` L43-44
- 問題: 「決めて理由を書く」とあるが、判断のために何を見ればよいかが曖昧。生成データだと `mart_product_sales` は注文済みの product だけが残るので、INNER でも LEFT でも結果集合がほぼ同じになる事実を初学者は気づかない。
- 提案: ヒントを拡張 ——
  ```markdown
  - **JOIN 方向の判断材料**:
    1. `mart_product_sales` には注文ゼロの product が含まれない可能性がある
       (`int_order_details` 起点の集計なので)
    2. `int_product_reviews` はレビューがある全商品 (今回は 100 種類) を含む
    3. 「レビュー満点だが注文ゼロ」の商品をランキングに残したいか？
       - 残したい → LEFT JOIN + COALESCE(0)
       - 売れていない商品はランキング無価値 → INNER JOIN
    自分の選択を `mart_top_rated_products.sql` 冒頭にコメントで残すと
    後で読み返したときに思考が辿れる。
  ```

#### 🟢 [m-08] Exercise 05 の seed CSV 47 行を学習者に手書きさせるかどうかの選択が曖昧

- 場所: `docs/exercises/05-seeds-and-macros.md` L41-54
- 問題: 「区分の例」表だけ提示し「学習者の解釈は自由」とあるが、47 都道府県の region 分類は社会通念依存（沖縄を九州に入れるか否か）。学習者によって seed のテストが落ちうる。
- 提案: 「解答例の CSV をコピペで OK」と明示し、学習意図は「seed の宣言・schema・accepted_values」にあることを示す。region 分類論議は範囲外。

#### 🟢 [m-09] Exercise 共通: 進捗の「ロールバック手順」が無い

- 場所: `docs/exercises/README.md` L57
- 問題: 「`dbt/models/exercises/` を丸ごと削除」とあるが、`raw.reviews` `raw.orders_increment` `staging.prefectures` `snapshots.snap_products` `marts.mart_top_rated_products` などはどう消すかに言及していない。
- 提案: README に「練習問題のリセット手順」を追加 ——
  ```sql
  DROP TABLE IF EXISTS raw.reviews CASCADE;
  DROP TABLE IF EXISTS raw.orders_increment CASCADE;
  DROP TABLE IF EXISTS staging.prefectures CASCADE;
  DROP SCHEMA IF EXISTS snapshots CASCADE;
  ```
  「+ `dbt/models/exercises/` `dbt/seeds/exercises/` `dbt/snapshots/exercises/` `dbt/macros/exercises/` `dbt/tests/exercises/` を `rm -rf`」。

---

### 7. テスト・品質保証

#### 🟡 [M-19] `dbt test` が落ちたときの調査手順が無い

- 場所: README, ADR-0008
- 問題: `dbt test` が PASS=61 になることは README §13 完了条件にあるが、落ちた場合の対処（どのテストが落ちたか／どの行が違反か／`dbt test --store-failures` の使い方／`target/run/<test>.sql` の見方）がどこにも書かれていない。
- 提案: README または concepts.md に「テストが落ちたら」セクション ——
  ```markdown
  ## dbt test が落ちたら

  1. ログ末尾に出る `Failure in test ...` のテスト名をコピー
  2. `target/run/local_analytics/<schema>/<test_name>.sql` を `cat`
     - これが「dbt が DB に投げた SQL」の compiled 形
  3. `psql` でその SQL を直接流す → 違反行が見える
  4. 永続化したい場合: `dbt test --store-failures`
     - `target_schema_<...>__<test>` のような失敗行 table が残る
  5. 修正方針:
     - generic test (`schema.yml`): データ側を直す or テストを緩める
     - singular test (`tests/*.sql`): WHERE 条件を見直す
  ```

#### 🟢 [m-10] `smoke_test.py` の strict / warn 設計の意義が docs から発見しづらい

- 場所: `scripts/smoke_test.py` L1-35、ADR-0008
- 問題: docstring は丁寧だが、README からは smoke_test.py の存在 / 使い方が「補助: scripts/smoke_test.py も ...」(L218) と 1 行しか触れられていない。strict と warn の境界線（spec §11.3 の 3 項目だけ厳密）が他者にとって見つけにくい。
- 提案: README §「テスト・品質保証」セクション（新設）で smoke_test.py の使い方・終了コードを 1 段落で紹介、ADR-0008 へのリンクを置く。

---

### 8. 再現性・可搬性

#### 🟡 [M-20] 「クリーンスレートからの構築」を README + docs だけで再現する手順がパラパラに散っている

- 場所: `README.md`, `ADR-0009 §5`, `docs/exercises/README.md`
- 問題: 再構築手順は ADR-0009 §5 にあるが README からのリンクが無い。新マシンで同じ環境を作りたい人は ADR-0009 まで掘らないと到達できない。
- 提案: README 末尾に「ゼロから再現する」セクションを追加し、ADR-0009 §5 のスクリプトをそのまま転記 or リンク。

#### 🟡 [M-21] Metabase ボリュームの破棄手順が「環境により異なる」で終わっている

- 場所: `docs/dashboard.md` L172
- 問題: `docker volume rm dbt-tutorial_metabase_data` の `dbt-tutorial_` プレフィックスは ADR-0010 で固定済 (project name = dbt-tutorial)。「環境により異なる」と書く必要は無い。
- 提案: 「`docker compose.yml` で `name: dbt-tutorial` を固定済みなので volume 名は常に `dbt-tutorial_metabase_data` （docker compose v2 標準）」と確定的に書く。

#### 🟢 [m-11] `data/raw/.gitkeep` などの空ファイルが文書化されていない

- 場所: `data/raw/.gitkeep`、`data/exercises/inbox/.gitkeep`
- 提案: README §ディレクトリ構成のコメント欄に「`.gitkeep` は CSV 生成前のディレクトリ存在保証。中身（`*.csv`）は gitignored」と書く。

---

### 9. アクセシビリティ・体験

#### 🟡 [M-22] 図解 (Mermaid) が README のアーキ図 (text art) のみ

- 場所: `README.md` L19-41
- 問題: text art は Apple Silicon の monospace 環境では崩れがち（特に罫線の `┌─┐` が幅違いで見える）。dbt の DAG（source → staging → intermediate → marts）も視覚化されていない。
- 提案: README に Mermaid を追加 ——
  ```mermaid
  flowchart LR
      CSV[Faker CSV<br/>data/raw/*.csv] -->|psycopg COPY| RAW[(raw schema<br/>customers/products/stores/orders)]
      RAW -->|stg_*<br/>view| STG[(staging schema)]
      STG -->|int_order_details<br/>view| INT[(intermediate schema)]
      INT -->|mart_*<br/>table| MART[(marts schema)]
      MART -->|readonly_user<br/>SELECT| BI[Metabase]
  ```

#### 🟢 [m-12] 専門用語の初出時に簡潔な定義が無いものがある

- 場所: 全般
- 提案: README 冒頭に語彙集 (Glossary) を追加 ——
  - **DWH** = Data Warehouse（分析用 DB の総称）
  - **ELT / ETL** = データ移送の順序の違い (Transform をどこでやるか)
  - **DAG** = Directed Acyclic Graph、依存グラフ。dbt が `ref()` から自動構築
  - **SCD Type-2** = Slowly Changing Dimension、履歴行追加方式
  - **DDL / DML** = Data Definition / Manipulation Language

#### 🟢 [m-13] 日本語と英語の混在ポリシーが暗黙

- 場所: 各種ファイル
- 問題: ADR / README は日本語ベース、コードコメント / spec の表は英語混じり、Faker LOCALE は ja_JP、Metabase の MB locale も ja。一方で dbt の description は英語で書かれている。これは「コード/技術用語=英語、説明=日本語」というポリシーらしいが明文化されていない。
- 提案: `CONTRIBUTING.md` か README に「言語ポリシー: 説明・ドキュメント本文は日本語、SQL/yml の description やコード comment は英語（dbt docs / OSS 表記との互換のため）」と一文。

---

### 10. 学習導線

#### 🟡 [M-23] 「phase 完了 → 練習問題 → ダッシュボード」の順序サインポストが弱い

- 場所: `README.md`、`docs/exercises/README.md`、`docs/dashboard.md`
- 問題: README の最後に「次フェーズ候補（spec §14）」があるが、その手前の「練習問題」「ダッシュボード」が同列の参照にしか見えない。学習者の最適経路（最初に何をやるべきか）が示されていない。
- 提案: README 末尾に "学習ロードマップ" セクションを追加 ——
  ```markdown
  ## 学習ロードマップ

  推奨順:
  1. **README §クイックスタート** で `dbt run` / `dbt test` を成功させる
  2. **`docs/dashboard.md`** で Metabase を立ち上げ、marts の中身を可視化する
     （SQL 結果が「画面で見える」ようになると学習意欲が上がる）
  3. **`docs/exercises/`** の 5 問を順に解く
     - 01: 新しい source/staging を足す → CRUD の感覚
     - 02: 集計マートを足す → ビジネスロジックの局所化
     - 03: incremental → 大規模化への第一歩
     - 04: snapshot → 履歴化と SCD Type-2
     - 05: seed + macro → DRY と再利用
  4. **次フェーズ候補（ADR-0009 §4）**: Airflow / クラウド DWH / CI/CD / dbt-utils
  ```

#### 🟡 [M-24] 「卒業後の発展」への入り口が ADR-0009 §4 に閉じ込められている

- 場所: `docs/decisions/0009-project-completion-summary.md` §4
- 問題: README からは「次フェーズ候補（spec §14）」リスト程度しか見えず、ADR-0009 §4 の表（Airflow / dbt-bigquery / GitHub Actions / Metabase / Great Expectations）が深くまで掘らないと出てこない。
- 提案: README に上記表をダイジェスト引用するか、`docs/next-steps.md` を新設して各候補のスタータ記事リンクを集める。

#### 🟢 [m-14] phase-NN/task-MMM ファイル群が学習者にとって "プロジェクト遂行ログ" 以上の意味を持ちうる

- 場所: `docs/tasks/phase-NN/task-MMM.md`
- 提案: `docs/tasks/README.md` に「これは開発時の作業ログ。学習者は読まなくて良いが、『なぜこの順序で組んだか』を追体験できる」と注意書き。

---

## 推奨対応リスト（優先順）

1. **C-01 (Critical)**: uv のインストール手順を `brew install uv` に確定し、Python 3.12 が uv 経由で取得されることを明記
2. **C-02 (Critical)**: `set -a; source .env; set +a` の意味と必要性を README にコラムで説明
3. **C-03 (Critical)**: cwd 規約をクイックスタート冒頭で定義し、各コードブロックに `# cwd:` を入れる
4. **C-04 (Critical)**: `docs/concepts.md` 新設、または README に raw/staging/intermediate/marts の責務分離を概念解説として追加
5. **C-05 (Critical)**: README に「dbt とは」「ELT とは」「IaC とは」のコア概念節を追加
6. **C-06 (Critical)**: `docs/spec2.md` を deprecated 注記つきに変更（または `archive/` へ移動）
7. **M-01**: credsStore 削除を「前提」セクションに昇格
8. **M-04**: `get_custom_schema.sql` のコメントに「無効化した場合の挙動」サンプルを追加
9. **M-05**: README に dbt_user / readonly_user 分離の理由を 1 段落
10. **M-07**: ADR 0003 / 0007 欠番の経緯メモ
11. **M-08**: README §ドキュメントに dashboard.md / ADR-0010 を追加
12. **M-14**: README §トラブルシュートに「エラー文字列 → 対処」逆引き表
13. **M-16**: Exercise 03 Step 3 の解答コードを本文から削除
14. **M-17**: Exercise 04 の Step 0（snapshots schema 作成）を新設
15. **M-19**: 「dbt test が落ちたら」のセクションを追加
16. **M-22**: README に Mermaid アーキ図
17. **M-23**: README 末尾に学習ロードマップを追加
18. **m-01〜m-14**: 余裕がある時に順次

## 良かった点（残してほしい設計）

- **ADR が判断ログとして十全に機能している**: なぜ INNER JOIN か / なぜ table か / なぜ accepted_values は category だけか / なぜ smoke の strict は §11.3 厳守か、すべて自然言語で残っている。後発エンジニアが「設計の `WHY` を辿れる」教材としての価値は非常に高い。
- **dbt_user / readonly_user の責務分離**: 学習用最小構成でありながら本番設計の素地を持っている。クラウド DWH への切替やセキュリティ強化フェーズで自然に活きる。
- **scripts/*.py の docstring が丁寧**: モジュール冒頭の解説が「何をする」「なぜ」「冪等性戦略」「接続ロール」まで網羅されており、コード単体で読める。
- **生成データが固定 seed (42 / 101 / 104) で完全再現可能**: 複数の学習者が同じ手順で同じテスト結果を得られるため、教材として大きな利点。
- **smoke_test.py の strict / warn 分離思想が明文化**: ADR-0008 で「spec 契約を勝手に強化しない」「diagnostics は warn で出す」「fail-fast 5 秒」「[FAIL] プレフィックス grep」と運用設計が腹落ちする粒度で説明されている。これは新しいプロジェクトでも転用できる思想。
- **練習問題の難易度勾配**: 01 (CSV 取り込み) → 02 (集計マート) → 03 (incremental) → 04 (snapshot) → 05 (seed + macro) は dbt の主要機能を網羅しつつ、独立しても解ける構造（前提依存は 02 のみ）。学習者が好きな順で攻められる柔軟性がある。
- **Metabase bootstrap の冪等戦略**: `name` ベース upsert / `has-user-setup` で初回判定 / Setup API + login fallback の二経路、と「再実行で何が起きるか」が予測可能。学習用ツールとしての堅牢性が高い。
