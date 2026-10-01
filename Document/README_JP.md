# DiscordBot_Servercontroller

## 概要

Discord.py で作成した Discord Bot です。メンバー・ロール・チャンネルの管理、CSV によるロール設定の一括更新などを行えます。

## セットアップ

### コードを使用する場合

1. Python 3.10 以降を用意します。
2. discord.py をインストールします。

```powershell
pip install discord.py
```

3. `Src/config/config.json` に Bot トークンを設定します。

```json
{
   "BOT_TOKEN": "Botのトークン"
}
```

4. Discord Developer Portal で、Bot の以下の Intent を有効にします。
   - Message Content Intent
   - Server Members Intent
   - Reactions と Voice States はコードで使用しています。

5. 起動します。

```powershell
python Src/bot_main.py
```

### テスト

開発用依存関係をインストールして、プロジェクトルートからテストを実行します。

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

### exeを使用する場合

Pythonがインストールされていない環境では、`release`フォルダ内のexeを使用できます。

1. `release/config/config.json` に Bot トークンを設定します。

```json
{
   "BOT_TOKEN": "Botのトークン"
}
```

2. `release/DiscordBot_Servercontroller.exe`を実行します。

exe版ではPythonやdiscord.pyのインストールは不要です。処理結果のCSV・ZIPは`release/temp`に一時保存され、Discordへの送信後に削除されます。

Bot トークンは公開せず、設定ファイルを Git にコミットしないでください。

## コマンド

コマンドはスラッシュコマンド形式で利用します。`/help` で利用可能なコマンド一覧を表示できます。

### 共通機能

```text
/help
```

### メンバーロール機能

```text
/member role add @メンバー ロール名
/member role get ユーザー名
/member role set + CSVファイル
/member role template
/member role remove @メンバー ロール名
```

CSV形式は [テンプレートファイル](#テンプレートファイル) の `member_role_template.csv` を参照してください。

`get` はDiscordユーザー名に一致するメンバーのロール一覧を返信します。メンションで指定することもできます。現在、CSVではなくテキスト返信です。`set` CSVの「ユーザー名」列もDiscordユーザー名を指定します（大文字小文字は区別しません）。

`set` は処理結果を `result` 列、失敗理由を `reason` 列に記録したCSVを返信します。

`add`、`set`、`remove` には「ロールの管理」権限が必要です。

### サーバーロール機能

```text
/server role add ロール名
/server role edit ロール名 権限名 on|off
/server role edit ロール名 color #RRGGBB
/server role permissions
/server role get
/server role set + CSVファイル
/server role template
/server role remove ロール名
```

CSV形式は [テンプレートファイル](#テンプレートファイル) の `server_role_template.csv` を参照してください。

`/server role permissions` で、権限名・英語説明・日本語訳・設定可能な値（`on` / `off`）を記載したCSVを取得できます。

`/server role get` が出力するCSVは `/server role set` に添付して再利用できます。`set` の結果CSVには `result` と `reason` 列が追加されます。

`add`、`edit`、`set`、`remove` には「ロールの管理」権限が必要です。

### メンバー一覧機能

```text
/server member list
```

サーバーのメンバー一覧をCSVファイルで取得します。CSVが大きい場合は、通信時間を短縮するためZIP形式で返信します。

### チャンネル機能

```text
/channel create text チャンネル名 [カテゴリー名]
/channel create voice チャンネル名 [カテゴリー名]
/channel move #チャンネル カテゴリー名
/channel get
/channel set + CSVファイル
/channel template
```

チャンネルの作成・移動には「チャンネルの管理」権限が必要です。指定したカテゴリーが存在しない場合は自動作成します。

`/channel get` でサーバーのチャンネル一覧を `name,type,category` 形式の CSV ファイルとして取得できます。

このCSVは `/channel set` に添付して再利用できます。結果CSVには `result` と `reason` 列が追加されます。ロール列を1つ以上指定した場合は記載ロールだけにアクセスを許可し、未記載ロールの既存アクセス許可を解除します。ロール列が空の場合は既存権限を維持します。`user_1`、`user_2` などの列にはDiscordユーザー名を指定でき、該当メンバーへチャンネルアクセスを追加します。既存のユーザー別権限は変更しません。

CSV形式は [テンプレートファイル](#テンプレートファイル) の `channel_template.csv` を参照してください。

`type` には `text` または `voice` を指定します。既存チャンネルは名前で検索してカテゴリーを変更し、存在しない場合は新規作成します。カテゴリーが存在しない場合は自動作成します。

### チャット添付ファイル機能

```text
/chat get #テキストチャンネル [開始日 YYYY-MM-DD] [拡張子]
/chat get + CSVファイル
/chat template
```

チャンネルをメンションすると、単一チャンネルの添付ファイルを取得できます。開始日は省略可能で、指定する場合は `YYYY-MM-DD` 形式です。指定日の00:00（UTC）以降が対象になります。拡張子は `png` または `.png` の形式で指定でき、`png|jpg|gif` のように複数指定できます。

CSVに `category_name,channel_name,start_date,extension` を指定すると、各行のチャンネルから開始日以降の添付ファイルを取得し、`カテゴリー名/チャンネル名/ファイル名` の構成で1つの ZIP ファイルにまとめて返信します。`start_date` または `extension` を空欄にすると、その条件では絞り込みません。実行には「メッセージの管理」権限が必要です。

CSV形式は [テンプレートファイル](#テンプレートファイル) の `chat_template.csv` を参照してください。

### イベント通知機能

以下はサンプル機能です。運用環境の要件に合わせて、処理内容や通知先を変更・無効化してください。

- ボイスチャンネルへ参加・退出すると、対象ボイスチャンネルのテキストチャットへ通知します。
- 新規メンバー参加時は、参加ログを出力します。

### シナリオ進行機能

```text
/scenario template
/scenario set + CSVファイル
/scenario list
/scenario start シナリオID [開始step]
/scenario delete シナリオID
/scenario export
```

シナリオは `Src/config/scenario_definitions.json` に保存され、サーバーごとの進行状態は `Src/config/scenario_states.json` に保存されます。`/scenario set` は既存のシナリオを保持したままCSVの内容を追記します。同じシナリオIDとステップ番号がある場合は更新されます。登録結果を `result` / `reason` 列に記録したCSVを返信します。`/scenario export` のCSVは `/scenario set` に再利用できます。

CSV形式と `welcome` シナリオの例は [テンプレートファイル](#テンプレートファイル) の `scenario_template.csv` を参照してください。

`completion_type` が `reaction` の場合、現在の指示メッセージにリアクションが付くと次へ進みます。`completion_value` が `*` または空欄なら任意のリアクション、絵文字を指定した場合はその絵文字だけが有効です。リアクション条件の指示メッセージには、見本となるリアクションが自動で追加されます。

複数の分岐は、1行に `branch_reaction_N` と `branch_step_N` の列を追加して指定できます。分岐先は現在のシナリオ内のstepに限定されます。

## テンプレートファイル

CSVテンプレートは `Src/templates` の用途別フォルダにあります。必要なCSVを編集して各コマンドに添付してください。

### Set 入力

- [channel_template.csv](../Src/templates/set/input/channel_template.csv): チャンネル設定
- [member_role_template.csv](../Src/templates/set/input/member_role_template.csv): メンバーロール設定
- [server_role_template.csv](../Src/templates/set/input/server_role_template.csv): サーバーロール設定
- [scenario_template.csv](../Src/templates/set/input/scenario_template.csv): シナリオ登録
- [team_match_scenario.csv](../Src/templates/set/input/team_match_scenario.csv): チーム戦シナリオ例

### Get 入力

- [chat_template.csv](../Src/templates/get/input/chat_template.csv): 複数チャンネルの添付ファイル取得

### 応答・結果の配置

- [Set応答フォルダ](../Src/templates/set/response/README.md): Setの結果CSVについて
- [Get結果フォルダ](../Src/templates/get/result/README.md): Getの出力について

応答・結果ファイルは`temp`フォルダへ一時保存され、Discordの添付ファイルとして返信した後に削除されます。

## ライセンス

- [プロジェクトライセンス（MIT）](licenses/LICENSE)
- [第三者OSSライセンス一覧](licenses/THIRD_PARTY_LICENSES.md)
