# アプリ構造ドキュメント

## 1. 概要

Discordサーバーの運用を支援するBotです。メンバー・ロール・チャンネル管理、添付ファイル取得、シナリオ進行、イベント通知を提供します。コードと実行時データは `Src/` に配置し、ドキュメントは `Document/` に配置しています。

Botのエントリーポイントは `Src/bot_main.py` です。ルートの `run_bot.cmd` からも起動できます。

`Src/tools/scenario_editor/` のシナリオエディターは、CSVまたはCSVを含むフォルダを開き、シナリオやステップの内容・分岐をGUIで編集して元のCSVに上書き保存するツールです。選択したフォルダ直下のCSVから、シナリオIDとファイル名を表示して対象を選択できます。完了条件がリアクションの場合や分岐リアクションは、検索可能なUnicode絵文字一覧から選択できます。

## 2. ディレクトリ構成

```text
Src/
  bot_main.py
  event/                   Discordイベントとコマンド
  function/                共通ロジックとサービス
  config/                  Bot設定、シナリオ定義・進行状態
  templates/
    set/input/              Set用CSV入力
    set/response/           Set応答の分類
    get/input/              Get用CSV入力
    get/result/              Get結果の分類
  test/                    テスト
  tools/scenario_editor/   シナリオ編集GUIツール(tkinter)
  tools/config_editor/     設定編集GUIツール(tkinter)
  tools/template_editor/   テンプレートCSV編集GUIツール(tkinter)

Document/
  README_JP.md / README_EN.md
  ARCHITECTURE_JP.md / ARCHITECTURE_EN.md

run_bot.cmd                Bot起動用バッチ
```

## 3. 主な責務

### `Src/bot_main.py`

DiscordクライアントとIntentsを設定し、スラッシュコマンドおよびイベントハンドラを登録してBotを起動します。

### `Src/event/`

Discordイベントとコマンドの入口です。`on_ready`、メッセージ、リアクション、メンバー参加、ボイス状態の各イベントを扱います。各コマンドは `event/on_message/command/` にあります。

### `Src/function/`

イベントやコマンドから呼び出す共有処理をまとめています。シナリオ管理、Discord操作、ファイル処理、セキュリティ関連の処理を含みます。

### `Src/config/`

`config.json` にBot設定を保存します。`scenario_definitions.json` はシナリオ定義、`scenario_states.json` はサーバーごとの進行状態を保持します。

### `Src/templates/` と `Src/tools/`

CSV等の成果物を用途別に `Src/templates/set/input/`、`set/response/`、`get/input/`、`get/result/` に分類しています。Set応答とGet結果は実行時に各出力フォルダへ保存し、Discordにも添付します。生成ファイルはGit管理対象外です。`Src/tools/scenario_editor/` はシナリオCSVの確認・編集用ツールです。

## 4. コマンド処理

```text
Discord interaction
  -> Src/event/on_message/command/slash_commands.py
  -> 各コマンドハンドラ
  -> Src/function/ の共通処理
  -> Discordへの応答
```

`slash_commands.py` はスラッシュコマンドと既存のコマンド処理をつなぐアダプターです。

## 5. CSVのGet・Set

- `/channel get` の `name,type,category` CSVは `/channel set` に利用できます。
- `/server role get` のロール設定CSVは `/server role set` に利用できます。
- `/scenario export` のシナリオCSVは `/scenario set` に利用できます。
- `/member role get` は現在CSVではなく、ロール一覧をテキストで返信します。`/member role template` が `/member role set` 用のCSV形式を提供します。

チャンネル・メンバーロール・サーバーロールの `set` は、入力CSVの各行に `result` と `reason` 列を加えた結果CSVを返信します。シナリオ登録は一括処理で、処理全体の成功または失敗理由を各データ行に記録します。入力に同名列がある場合は重複させず上書きします。

チャンネル設定でロール列が1つ以上指定されている場合、記載ロールだけにアクセスを許可し、未記載ロールの既存アクセス許可を解除します。ロール列が空の場合、既存のロール権限を変更しません。

## 6. シナリオの保存と進行

シナリオ定義は `Src/config/scenario_definitions.json`、サーバーごとの進行状態は `Src/config/scenario_states.json` に保存します。

```text
/scenario set -> CSVを登録・更新 -> scenario_definitions.json
/scenario start -> 初期状態を作成 -> scenario_states.json
メッセージまたはリアクション -> 次のステップを判定・送信
```

`/scenario set` は既存定義を保持し、CSV内のシナリオIDとステップ番号が一致する項目を更新します。

## 7. 拡張時の目安

1. コマンドやイベント入口を `Src/event/` に追加
2. 共通処理を `Src/function/` に実装
3. 必要に応じて `Src/config/` またはCSVテンプレートを更新
4. スラッシュコマンドを `slash_commands.py` に登録
