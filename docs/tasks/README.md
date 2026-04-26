# タスク管理

`phase-NN/task-MMM.md` 形式でタスクを管理する。CLAUDE.mdのルールに準拠。

## ステータス

- `Todo`: 未着手
- `InProgress`: 着手中（owner欄にエージェント識別子を記載）
- `Blocked`: 依存待ち or 判断待ち
- `Done`: 完了（受入条件すべてクリア）

## task記述フォーマット

```md
# task-MMM: <タイトル>

- Phase: NN
- Status: Todo
- Owner: -
- Depends on: phase-XX/task-YYY (任意)
- Parallelizable with: phase-NN/task-LLL (任意)

## 目的
## 入力 / 前提
## 成果物
## 受入条件
## 実装メモ / 判断ログ
```
