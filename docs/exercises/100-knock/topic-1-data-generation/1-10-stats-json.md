# 1-10: 生成データの行数・列・null 比率を `_stats.json` に書き出す (data contract)

## シナリオ

1-1〜1-8 で生成された CSV 群 (`customers.csv`, `products.csv`, `stores.csv`, `orders.csv`, `reviews.csv` …) は、後続トピックで dbt の `source.yml` に登録され、`freshness` / `not_null` / `accepted_values` テストの対象になる。
ただし、その前に **「上流 CSV 自身が今どんな形をしているか」を生成パイプラインの中で観測・記録** しておきたい。
これが「**自前 data contract**」の発想で、後の `dbt-expectations` や `source.freshness` よりも **手前** にあるレイヤー。
今回は、`data/100-knock/topic-1/*.csv` を全部読んで、行数・列・null 比率を `_stats.json` に書き出すスクリプトを書く。

## 学べること

- `pathlib.Path.glob('*.csv')` で対象ファイル列挙
- `csv.DictReader` で読みながら 1-pass で集計 (行数・列名・列ごとの null カウント)
- `json.dump(..., indent=2)` で人間が diff できる stats を書き出す
- 上流データの **最小プロファイル契約** をパイプライン内で生成する考え方
- dbt-expectations / source.freshness とのレイヤー分離 (「いつ・誰の責務で観測するか」)

## 前提

- **1-1 〜 1-8 を完了済み** (`data/100-knock/topic-1/` 配下に CSV が一式存在する)
- `requirements.txt` から Python 標準ライブラリのみで動く (Faker / pandas は不要)
- 出力先 `data/100-knock/topic-1/_stats.json` は既存 CSV 列挙時に **除外** する (拡張子で弾く)

## 入力データ

`data/100-knock/topic-1/*.csv` (1-1〜1-8 の出力すべて)。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_10_stats.py` を作る。

要件:

- 入力: `data/100-knock/topic-1/` 配下の全 `*.csv`
- 出力: `data/100-knock/topic-1/_stats.json`
- スキーマ:
  ```json
  {
    "generated_at": "2026-04-28T10:30:00Z",
    "files": {
      "customers.csv": {
        "rows": 1000,
        "columns": ["customer_id", "customer_name", "email", "created_at"],
        "null_ratio": {"customer_id": 0.0, "customer_name": 0.0, "email": 0.0, "created_at": 0.0}
      },
      "orders.csv": {
        "rows": 10000,
        "columns": [...],
        "null_ratio": {...}
      }
    }
  }
  ```
- `null_ratio` は **空文字 `""` を null とみなす** (CSV では NULL = 空フィールド)
- `null_ratio` の値は `0.0` 〜 `1.0` の float (例: 10% NULL なら `0.1`)
- ファイル列挙時に `_stats.json` 自身など `.csv` 以外は除外
- 出力 JSON は `indent=2` で人間 diff フレンドリー
- `generated_at` は ISO 8601 UTC (`datetime.now(timezone.utc).isoformat()` 等。**冪等性ではなく観測時刻** なのでここは現在時刻で OK)

### Step 2: 実行

```bash
python3 scripts/100-knock/topic-1/generate_1_10_stats.py
# Wrote data/100-knock/topic-1/_stats.json: 8 files profiled
```

確認:

```bash
cat data/100-knock/topic-1/_stats.json | python3 -m json.tool | head -30
python3 -c "import json; s=json.load(open('data/100-knock/topic-1/_stats.json')); print(s['files']['customers.csv']['rows'])"
# => 1000
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-10-stats-json.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_10_stats.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/_stats.json` が 100 bytes 以上で生成される
- [ ] 生成 JSON が `json.load()` 可能
- [ ] `files["customers.csv"]["rows"]` が `1000`
- [ ] `files["orders.csv"]["rows"]` が `10000`

## ヒント (詰まったら)

- ファイル列挙: `for csv_path in sorted(Path("data/100-knock/topic-1").glob("*.csv")): ...`。`sorted` を入れると JSON の出力順が決まって diff しやすい。
- 行数と null カウントは **1-pass** でやる: `csv.DictReader` で 1 行ずつ読みながら `row_count += 1`、各列について `if value == "" or value is None: null_counts[col] += 1`。
- `null_ratio` は `null_counts[col] / row_count` (ゼロ割は `row_count == 0` で別扱い)。
- `generated_at` の形式: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`。**注意**: ここは観測時刻なので毎回違って OK。冪等にする必要はない (1-9 とは責務が違う)。
- `_stats.json` は **CSV じゃない** ので `glob('*.csv')` で勝手に除外されるが、念のため `if csv_path.name.startswith("_"): continue` を入れておくと安全。
- 「pandas で十分では?」と思うかもしれないが、標準ライブラリだけで書けると CI の依存が減って嬉しい。`csv.DictReader` で十分。

## 解答例

詳細は [`1-10-stats-json.solution.md`](1-10-stats-json.solution.md) を参照。
