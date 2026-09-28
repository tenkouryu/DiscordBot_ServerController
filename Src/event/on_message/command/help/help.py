import discord


"""
    利用可能なDiscordコマンドのヘルプを管理する。

    get_command_help_text:
        コマンド一覧の表示文を返す。

    main:
        コマンド一覧をチャンネルへ送信する。
"""


def get_command_help_text() -> str:
    """利用可能なコマンド一覧の表示文を返す。"""
    return (
        "利用可能なコマンド一覧:\n"
        "/help - このコマンド一覧を表示\n"
        "/member role add @メンバー ロール名 - メンバーにロールを追加\n"
        "/member role get メンバー名 - メンバーのロール一覧を表示\n"
        "/member role set + CSVファイル - メンバーロールをCSVから更新\n"
        "/member role template - メンバーロールCSVテンプレート\n"
        "/member role remove @メンバー ロール名 - メンバーからロールを削除\n"
        "/server role add ロール名 - ロールを追加\n"
        "/server role edit ロール名 権限名 on|off - ロール権限を変更\n"
        "/server role edit ロール名 color #RRGGBB - ロール色を変更\n"
        "/server role permissions - ロール権限名・説明・設定値をCSVで取得\n"
        "/server role get - ロール一覧をCSVで取得\n"
        "/server role set + CSVファイル - CSVからロール設定を更新\n"
        "/server role template - サーバーロールCSVテンプレート\n"
        "/server role remove ロール名 - ロールを削除\n"
        "/server member list - メンバー一覧をCSVで取得\n"
        "/channel create text|voice チャンネル名 [カテゴリー名] - チャンネルを作成\n"
        "/channel move #チャンネル カテゴリー名 - チャンネルを移動\n"
        "/channel get - チャンネル一覧をCSVで取得\n"
        "/channel set + CSVファイル - CSVからチャンネルを設定\n"
        "/channel template - チャンネルCSVテンプレート\n"
        "/chat get #チャンネル [開始日] [拡張子] または + CSVファイル - 添付ファイルをZIPで取得\n"
        "/chat template - チャット添付ファイル取得CSVテンプレート\n"
        "/scenario template - シナリオCSVテンプレート\n"
        "/scenario set + CSVファイル - シナリオを登録\n"
        "/scenario start シナリオID [開始step] - シナリオを開始\n"
        "/scenario list - 登録済みシナリオ一覧\n"
        "/scenario delete シナリオID - シナリオを削除\n"
        "/scenario export - シナリオをCSVで出力"
    )


async def main(message: discord.Message) -> None:
    """利用可能なコマンド一覧を送信する。"""
    await message.channel.send(get_command_help_text())
