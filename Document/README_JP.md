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

### リマインド

`Src/config/reminders.json`（exe版は `release/config/reminders.json`）に予定を登録すると、Bot起動中に30秒ごとに確認し、指定日時にチャンネルへ通知します。日時は日本時間の `+09:00` を含むISO 8601形式、チャンネル・メンション先はDiscord IDで指定してください。

```json
{
  "reminders": [
    {
      "id": "meeting-20261030",
      "datetime": "2026-10-30T19:00:00+09:00",
      "channel_id": "123456789012345678",
      "content": "ミーティングを開始します。",
      "mention_users": ["234567890123456789"],
      "mention_roles": ["345678901234567890"]
    }
  ]
}
```

`id` は予定ごとに一意にしてください。通知に失敗した予定は設定に残り、再試行されます。成功した予定は設定から削除され、送信結果は `config/reminder_log.jsonl` に追記されます。

サーバー管理権限のあるユーザーは `/reminder add` で予定を登録し、表示されたIDを使って `/reminder remove` で送信前の予定を削除できます。日時は `YYYY-MM-DD HH:MM`（日本時間）または `+09:00` 付きISO 8601形式で指定します。

複数件は `/reminder template` で取得できるCSVに記入し、`/reminder import` に添付して一括登録できます。必須列は `datetime`、`channel_id`、`content`、任意列は `mention_users`、`mention_roles` です。メンション列にはユーザーの表示名またはDiscordユーザー名、ロール名を記入できます。複数対象は `;` 区切りです。名前は操作中のサーバー内で大文字・小文字を区別せず完全一致で検索し、該当なし・複数一致はエラーにします。従来どおりDiscord IDも指定できます。CSV全体を検証してから追加し、既存の予定は置き換えません。登録先チャンネルとメンション対象は操作中のサーバー内に限られます。

`/reminder add` はユーザー・ロールのDiscord選択欄から対象を選びます。Discordが選択対象を内部IDとして渡します。

## 補助GUIツール

設定・CSV・サーバーエクスポートJSONの編集機能は「サーバー設定統合エディター」に集約されています。Python環境ではリポジトリのルートから次のコマンドで起動できます。Windowsでは `release/tools/server_config_editor.exe` を利用できます。
### サーバー設定統合エディター

```powershell
python Src/tools/server_config_editor/server_config_editor.py
```

「設定」「テンプレート」「サーバーロール」「メンバーロール」「チャンネル」「シナリオ」「リマインダー」「サーバーエクスポート」をタブで切り替えて編集できます。CSV一覧の列見出しをクリックするとExcel形式のドロップダウンが開き、昇順・降順の並べ替え、値の検索、チェックボックスによる複数値の絞り込みができます。複数列の条件を組み合わせたり、空欄を選んだりできます。テンプレートはセルのダブルクリックで編集できます。メンバーロールCSVは列名から形式を自動判定し、保存時に入力を検証します。未保存の変更があるタブには `*` が付き、終了時に確認します。

サーバーロールCSVではロール名・色・権限の編集と権限列の追加・削除、メンバーロールCSVではロール列の追加・削除、チャンネルCSVでは`role_N`・`user_N`列の追加・削除ができます。シナリオタブではCSVファイルまたはフォルダを開き、ステップ指示・完了条件・返信・分岐を編集できます。リマインダータブでは予定の追加・編集・削除と設定JSONの保存ができます。サーバーエクスポートタブでは `/server export` のJSONを開き、サーバーロール・メンバーロール・チャンネルを編集して保存できます。設定タブではトークンなどの秘密情報がマスクされます。

Python版は既定で `Src/templates` と `Src/config` を使用し、Windowsの [server_config_editor.exe](../release/tools/server_config_editor.exe) は `release` 内の設定・テンプレートを使用します。別の設定ファイルを開くには各タブの「開く...」を使います。設定ファイルを公開したりGitにコミットしたりしないでください。

## コマンド

コマンドはスラッシュコマンド形式で利用します。`/help` で利用可能なコマンド一覧を表示できます。

```mermaid
flowchart TD
    A["コマンド"] --> B["共通<br/>/help"]
    A --> C["メンバー"]
    A --> D["サーバー"]
    A --> E["チャンネル"]
    A --> F["チャット添付ファイル"]
    A --> G["シナリオ"]

    C --> C1["ロール<br/>add / get / set / update<br/>template / remove"]
    D --> D1["ロール<br/>add / edit / permissions / get<br/>set / template / remove"]
    D --> D3["設定移行<br/>import / export"]
    D --> D2["メンバー<br/>list"]
    E --> E1["create / get / move<br/>set / template"]
    F --> F1["get / template"]
    G --> G1["template / set / list<br/>start / delete / export"]
```

### 共通機能

```text
/help
```

### メンバーロール機能

```text
/member role add @メンバー ロール名
/member role get ユーザー名
/member role set + CSVファイル
/member role update + メンバー一覧CSV
/member role template
/member role remove @メンバー ロール名
```

CSV形式は [テンプレートファイル](#テンプレートファイル) の `member_role_template.csv` を参照してください。

`get` はDiscordユーザー名に一致するメンバーのロール一覧を返信します。メンションで指定することもできます。現在、CSVではなくテキスト返信です。`set` CSVは「ユーザーID」を優先し、IDが空の場合は「ユーザー名」、次に「表示名」で検索します。ID列がない従来形式のCSVも引き続き利用できます。

`set` CSVの `ロール1`、`ロール2` などの列に複数ロールを指定できます。従来形式の `ロール` 列にも対応します。処理結果は `result` 列、失敗理由は `reason` 列に記録されます。

`update` は `/server member list` のCSVを編集して添付すると、`User ID` を優先してメンバーを特定します。ID列がない、または空欄の場合は `Name`（Discordユーザー名）、次に `Display Name` の順で検索し、各メンバーのロールを `Role1`、`Role2` などの列の内容へ置き換えます。結果CSVには `result` と `reason` 列が追加されます。デフォルトロールとBot・連携サービス管理のロールは変更されません。

`add`、`set`、`update`、`remove` には「ロールの管理」権限が必要です。

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
/server export
/server import + JSONファイル
```

サーバーのメンバー一覧をCSVファイルで取得します。`User ID`、`Name`、`Display Name`、`Role1`、`Role2` の列を出力し、ロールは個別の列に記載します。CSVが大きい場合は、通信時間を短縮するためZIP形式で返信します。

`/server export` はサーバーロール、メンバーごとのロール割り当て、チャンネル設定を1つのJSONファイルで取得します。ロール権限、チャンネルの種類・カテゴリー・設定、ロール/メンバーごとのチャンネル権限上書きも含みます。実行には「ロールの管理」と「チャンネルの管理」の両方の権限が必要です。

`/server import` にこのJSONを添付すると、最初に適用前のサーバー設定を `server_rollback_before_import_...json` というロールバック用ファイル名で返信し、その後サーバー設定をJSONと同期します。ロールバック用ファイルを再度 `/server import` に添付すると、適用前の状態へ戻せます。バックアップJSONの保存または送信に失敗した場合は、サーバー設定を変更しません。別サーバーへの移行ではロール名、メンバー名（必要に応じて表示名）、チャンネル名と種類で対象を対応付け、存在しない対象は作成します。JSONにない管理可能なロールとチャンネルは削除し、チャンネルの権限上書きとメンバーのロール割り当てはJSONの内容に置き換えます。JSONに記載のないメンバーからも管理可能なロールを解除します。メンバー自体は削除しません。Bot・連携サービスが管理するロールなどDiscord API上変更できない項目は保持され、結果CSVに記録されます。この処理は対象サーバーの設定を削除・変更するため、適用前にJSONエディターで内容を確認してください。適用結果は各対象の処理結果・失敗理由を記録したCSVで返信します。実行には「ロールの管理」と「チャンネルの管理」の両方の権限が必要です。

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
