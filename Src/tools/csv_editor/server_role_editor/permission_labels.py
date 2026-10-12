"""権限名(CSV列名)と画面表示用の日本語名の対応表。"""

PERMISSION_LABELS_JA: dict[str, str] = {
    "administrator": "管理者",
    "view_channel": "チャンネルを見る",
    "read_messages": "チャンネルを見る(旧名)",
    "manage_channels": "チャンネルの管理",
    "manage_roles": "ロールの管理",
    "manage_permissions": "権限の管理",
    "manage_expressions": "表現の管理",
    "create_expressions": "表現の作成",
    "manage_emojis": "絵文字の管理(旧名)",
    "manage_emojis_and_stickers": "絵文字とステッカーの管理(旧名)",
    "view_audit_log": "監査ログを表示",
    "view_guild_insights": "サーバーインサイトを見る",
    "manage_webhooks": "ウェブフックの管理",
    "manage_guild": "サーバー管理",
    "create_instant_invite": "招待を作成",
    "change_nickname": "ニックネームの変更",
    "manage_nicknames": "ニックネームの管理",
    "kick_members": "メンバーをキック",
    "ban_members": "メンバーをBAN",
    "moderate_members": "メンバーをタイムアウト",
    "send_messages": "メッセージを送信",
    "send_messages_in_threads": "スレッドでメッセージを送信",
    "create_public_threads": "公開スレッドの作成",
    "create_private_threads": "非公開スレッドの作成",
    "embed_links": "埋め込みリンク",
    "attach_files": "ファイルを添付",
    "add_reactions": "リアクションの追加",
    "use_external_emojis": "外部の絵文字を使用",
    "external_emojis": "外部の絵文字を使用(旧名)",
    "use_external_stickers": "外部のステッカーを使用",
    "external_stickers": "外部のステッカーを使用(旧名)",
    "mention_everyone": "@everyone、@here、全てのロールにメンション",
    "manage_messages": "メッセージの管理",
    "pin_messages": "メッセージをピン留め",
    "manage_threads": "スレッドの管理",
    "read_message_history": "メッセージ履歴を読む",
    "send_tts_messages": "テキスト読み上げメッセージを送信",
    "send_voice_messages": "ボイスメッセージを送信",
    "send_polls": "投票を作成",
    "create_polls": "投票を作成(旧名)",
    "use_application_commands": "アプリコマンドを使用",
    "use_external_apps": "外部のアプリを使用",
    "connect": "接続",
    "speak": "発言",
    "stream": "動画",
    "use_embedded_activities": "アクティビティを使用",
    "use_soundboard": "サウンドボードを使用",
    "use_external_sounds": "外部のサウンドを使用",
    "use_voice_activation": "音声検出を使用",
    "priority_speaker": "優先スピーカー",
    "mute_members": "メンバーをミュート",
    "deafen_members": "メンバーのスピーカーをミュート",
    "move_members": "メンバーを移動",
    "set_voice_channel_status": "ボイスチャンネルのステータスを設定",
    "request_to_speak": "スピーカー参加をリクエスト",
    "manage_events": "イベントの管理",
    "create_events": "イベントの作成",
    "bypass_slowmode": "低速モードの影響を受けない",
    "view_creator_monetization_analytics": "クリエイターの収益化アナリティクスを見る",
}


def permission_label(flag: str) -> str:
    """日本語名を返す。未登録の権限は英語名を読みやすく整形して返す。"""
    return PERMISSION_LABELS_JA.get(flag, flag.replace("_", " "))


def permission_display(flag: str) -> str:
    """一覧で識別しやすいよう、日本語名の後ろに列名を添える。"""
    label = PERMISSION_LABELS_JA.get(flag)
    return f"{label} ({flag})" if label else flag
