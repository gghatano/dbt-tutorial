# ADR 0004: raw 層ロード戦略 (DROP→CREATE→COPY)

- 日付: 2026-04-26
- ステータス: Accepted
- コンテキスト: phase-03/task-003 `scripts/load_raw_data.py`

## 決定

`scripts/load_raw_data.py` における raw 層 4 テーブルの再ロードは、
**`DROP TABLE IF EXISTS ... CASCADE` → `CREATE TABLE ...` → `COPY ... FROM STDIN`**
の3段で実装する。

## 検討した案

| 案 | 説明 | 採否 |
|---|---|---|
| A. DROP + CREATE + COPY | 毎回テーブルを作り直す | **採用** |
| B. TRUNCATE + COPY | スキーマを保ったまま中身だけ入れ替える | 不採用 |
| C. UPSERT / MERGE | 差分だけ反映 | 不採用 |

## 採用理由 (A)

1. **CSV のスキーマ変化に追従できる**: 列追加・型変更が起きた場合でも、`generate_dummy_data.py` の出力に合わせてテーブル定義を最新化できる。本タスクの範囲では列構造を `load_raw_data.py` 内 DDL がソースオブトゥルースとして保持する。
2. **冪等性が単純**: TRUNCATE は既存テーブルが存在することを前提とする。初回実行や別環境への移植を考えると `DROP IF EXISTS` の方が頑健。
3. **dbt source の名前解決には影響しない**: dbt は実行時に `raw.<table>` を `information_schema` 経由でバインドするため、間で DROP/CREATE が起きても次の `dbt run` で問題なく動作する。テストコードや過去の compile 結果を保持するための制約は存在しない。
4. **CASCADE の安全性**: 現フェーズでは raw テーブルに依存するビュー・FK は存在しない（dbt は materialized="table"/"view" で別 schema に書き込む）。仮に staging が view 化されても、`dbt run` で都度再構築されるので CASCADE しても実害なし。

## 不採用理由

- **B (TRUNCATE)**: 列構造の変更に追従できない、初回実行で AttributeError 相当のエラーになる、と扱いが面倒。raw 層の役割（spec §4: CSV をそのまま投入）を考えると、テーブルそのものを使い捨てる方が意図に近い。
- **C (UPSERT)**: raw 層に主キー以外の差分判定ロジックを置くのは責務逸脱。spec §4 の通り、変換は staging で行う。

## 関連する決定

- raw 層に **FK 制約は付けない**: spec §4 で「型変換、列名統一、軽微な正規化」は staging 層の役割と定義されているため、relational integrity は dbt staging の `relationships` テストで担保する（spec §8.2）。CSV を素直にそのまま受け取れることが raw 層の価値であり、上流由来のゴミも含めて取り込む方が将来のテスト網羅性に資する。
- 接続ロールに **`dbt_user` を使用**: Terraform で `raw` schema の所有者であり `CREATE/ALL` 権限を持つ。スーパーユーザーである `analytics_user` を使う必要は無く、最小権限の原則に沿う。dbt 本体も `dbt_user` で接続するため、ロード〜変換が同じロール所有のままシームレスに進む。
- COPY は **psycopg3 `cursor.copy()` の bytes ストリーム**で実装: `Path.open("rb")` で 64KiB チャンクを読み込んで `cp.write(chunk)` する。日本語データ（顧客名・都道府県）が含まれるため、テキストモードでの暗黙の encode/decode を避けたい。
