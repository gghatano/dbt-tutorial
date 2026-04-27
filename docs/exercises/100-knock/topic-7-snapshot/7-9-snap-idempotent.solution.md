# 7-9 解答例

## ゴール再掲

- `dbt snapshot --select snap_products_100knock` を **2 回連続** 実行
- 行数が 1 回目 = 2 回目 (= 入力が変わらないなら no-op)
- 「冪等性が成立している」 ことをエビデンス付きで示す

## 手順 (再掲)

```bash
set -a; source .env; set +a

# ----- 1) before -----
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 120

# ----- 2) snapshot 1 回目 -----
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
cd ..

# ----- 3) mid -----
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 120  (← Step 1 と同じ)

# ----- 4) snapshot 2 回目 -----
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
cd ..

# ----- 5) after -----
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 120  (← 1 回目・2 回目通じて変わらない = 冪等性 OK)
```

## 期待ログ (両回とも `SELECT 0`)

```text
06:00:00  Running with dbt=1.11.0
06:00:00  Found 1 snapshot, ...
06:00:01  Concurrency: 4 threads
06:00:01
06:00:01  1 of 1 START snapshot snapshots.snap_products_100knock .............. [RUN]
06:00:01  1 of 1 OK   snapshotted snapshots.snap_products_100knock ........... [SELECT 0 in 0.18s]
06:00:01
06:00:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`SELECT 0` の意味:

- snapshot は内部で「source 側現状 vs snapshot 側現役行」 を比較し、
  変化があった行を新規 INSERT する merge 文を組み立てる
- 入力 raw_100knock.products が 1 文字も変わっていなければ「変化のあった
  行 = 0 件」 で、INSERT も UPDATE も走らない (`SELECT 0` = 0 行 INSERT)
- 副作用 0 = テーブルの中身は寸分違わず同じ = **冪等**

## 冪等性が破れる例 (本問では起きないが、知識として)

| 条件 | 挙動 |
|---|---|
| `check_cols=['*']` で全列監視、source 側に `created_at` が毎秒更新 | 毎回 INSERT が走り履歴が無限膨張 |
| `unique_key` を間違えて常に新値になる列 (例: ULID 列) | 全行が「新しい行」と判定され、初回以外も毎回全行 INSERT |
| snapshot 中に raw を更新するパイプラインが並行で走る | レース条件で 2 回叩いた結果が変わる |

→ どれも「snapshot は冪等という前提」が崩れる。setting と運用設計の
セットで初めて冪等性が成立する。

## 採点 yaml の意図

採点側でも実際に 2 回 snapshot を叩く:

```yaml
# 抜粋
- id: snapshot-twice
  type: shell_command
  command: |
    cd dbt
    ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
    ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock

- id: row-count-stable-after-double-snapshot
  type: sql_assert
  sql: SELECT count(*)::int FROM snapshots.snap_products_100knock
  op: eq
  expected: 120
```

**`expected: 120`** は 「7-2 で v2 投入後の状態 = v1 100 + 改定 20 = 120 行」
を前提にしている。7-1 だけ完了で v2 未投入だと 100 行になる (7-2 完了が前提)。

## 解説まとめ

1. **冪等性 = 同じ入力に同じ結果**: dbt の設計原則。`dbt run` も `dbt test`
   も `dbt snapshot` も全部冪等であるべき。これが成立するから「とりあえず
   もう 1 回叩く」が安全な対処として機能する。
2. **snapshot の冪等性は `check_cols` 設計に依存**: ここを誤ると毎回履歴が
   増えて壊れる。「**業務上意味のある列だけ** check_cols に入れる」 が原則。
   `created_at` / `updated_at` のようなメタ列は入れない (= 値の変化を
   業務イベントと混同しないため)。
3. **`SELECT 0` ログを見て「失敗」と勘違いしない**: 0 件 INSERT は no-op =
   正常な「何もしなくて良かった」状態。失敗は `ERROR=N>0` で出る。ログ末尾
   の `Done. PASS=N ERROR=0` が成功の判定基準。
4. **本番 cron / CI リトライで効く性質**: Airflow / GitHub Actions の
   `retry: 3` で同じ snapshot job が 3 回走っても、初回成功なら 2〜3 回目
   は no-op。冪等でない pipeline ではこれが事故になる。
5. **次の問 (7-10)**: 個別 snapshot ファイルにいちいち `target_schema:`
   `strategy:` を書くのは冗長。`dbt_project.yml` の `snapshots:` セクション
   で **プロジェクト既定** を宣言し、各 snapshot ファイルから重複を消す。
