import csv
import io
import re

import discord
from function.file.template_output_service import save_template_output, send_template_output


_PERMISSION_DESCRIPTIONS_JA = {
    "add_reactions": "メッセージにリアクションを追加する",
    "administrator": "すべての権限を持ち、チャンネルごとの権限設定を無視する",
    "attach_files": "メッセージにファイルを添付する",
    "ban_members": "メンバーをサーバーからBANする",
    "bypass_slowmode": "低速モードの投稿間隔制限を無視する",
    "change_nickname": "自分のニックネームを変更する",
    "connect": "ボイスチャンネルに接続する",
    "create_events": "サーバーイベントを作成する",
    "create_expressions": "カスタム絵文字やスタンプなどを作成する",
    "create_instant_invite": "サーバーへの招待を作成する",
    "create_polls": "投票を作成する",
    "create_private_threads": "プライベートスレッドを作成する",
    "create_public_threads": "公開スレッドを作成する",
    "deafen_members": "メンバーのボイス音声を聞こえなくする",
    "embed_links": "メッセージにリンクの埋め込みを表示する",
    "external_emojis": "他のサーバーの絵文字を使用する",
    "external_stickers": "他のサーバーのスタンプを使用する",
    "kick_members": "メンバーをサーバーからキックする",
    "manage_channels": "チャンネルを作成・編集・削除する",
    "manage_emojis": "カスタム絵文字を管理する",
    "manage_emojis_and_stickers": "カスタム絵文字とスタンプを管理する",
    "manage_events": "サーバーイベントを編集・削除する",
    "manage_expressions": "カスタム絵文字やスタンプなどを管理する",
    "manage_guild": "サーバー設定を変更する",
    "manage_messages": "他のメンバーのメッセージを管理する",
    "manage_nicknames": "他のメンバーのニックネームを変更する",
    "manage_permissions": "ロールやチャンネルの権限設定を管理する",
    "manage_roles": "ロールを作成・編集・削除し、メンバーへ割り当てる",
    "manage_threads": "スレッドを管理する",
    "manage_webhooks": "Webhookを作成・編集・削除する",
    "mention_everyone": "@everyoneや@here、全ロールへのメンションを使用する",
    "moderate_members": "メンバーにタイムアウトを設定・解除する",
    "move_members": "メンバーを別のボイスチャンネルへ移動する",
    "mute_members": "メンバーのマイクをミュートする",
    "pin_messages": "メッセージをピン留めする",
    "priority_speaker": "優先スピーカーを使用する",
    "read_message_history": "チャンネルの過去のメッセージを読む",
    "read_messages": "チャンネルのメッセージを読む（旧権限）",
    "request_to_speak": "ステージチャンネルで発言をリクエストする",
    "send_messages": "メッセージを送信する",
    "send_messages_in_threads": "スレッド内にメッセージを送信する",
    "send_polls": "投票を送信する",
    "send_tts_messages": "読み上げメッセージを送信する",
    "send_voice_messages": "ボイスメッセージを送信する",
    "set_voice_channel_status": "ボイスチャンネルのステータスを設定する",
    "speak": "ボイスチャンネルで発言する",
    "stream": "ボイスチャンネルで画面共有や配信をする",
    "use_application_commands": "スラッシュコマンドなどのアプリコマンドを使用する",
    "use_embedded_activities": "ボイスチャンネルで埋め込みアクティビティを使用する",
    "use_external_apps": "外部アプリをサーバー内で使用する",
    "use_external_emojis": "他のサーバーの絵文字を使用する",
    "use_external_sounds": "他のサーバーのサウンドを使用する",
    "use_external_stickers": "他のサーバーのスタンプを使用する",
    "use_soundboard": "サウンドボードを使用する",
    "use_voice_activation": "音声検出で発言する",
    "view_audit_log": "サーバーの監査ログを閲覧する",
    "view_channel": "チャンネルを閲覧する",
    "view_creator_monetization_analytics": "クリエイター収益化の分析情報を閲覧する",
    "view_guild_insights": "サーバーのインサイトを閲覧する",
}


"""
    サーバーロールで指定可能な権限名一覧を表示する。

    create_permission_csv:
        権限名、説明、設定可能な値をCSVに変換する。

    main:
        権限名一覧をチャンネルへ送信する。
"""


def create_permission_csv() -> bytes:
    """discord.pyが受け付ける権限名と説明をCSVへ変換する。"""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["権限名", "権限の説明", "権限の説明（日本語）", "設定可能な値"]
    )

    for permission_name in sorted(discord.Permissions.VALID_FLAGS):
        description = getattr(discord.Permissions, permission_name).__doc__ or ""
        description = re.sub(r":class:`bool`:\s*", "", description)
        description = re.sub(r"\n\s*\.\. versionadded::.*", "", description, flags=re.S)
        description = " ".join(description.split())
        description_ja = _PERMISSION_DESCRIPTIONS_JA.get(
            permission_name,
            f"未翻訳: {description}",
        )
        writer.writerow([permission_name, description, description_ja, "on / off"])

    return output.getvalue().encode("utf-8-sig")


async def main(message: discord.Message) -> None:
    """ロール設定に使える権限名一覧CSVを送信する。"""
    result_path = save_template_output(
        "get/result",
        "role_permissions",
        create_permission_csv(),
    )
    await send_template_output(
        message.channel,
        "ロール権限名、説明、設定可能な値の一覧です。",
        result_path,
    )
