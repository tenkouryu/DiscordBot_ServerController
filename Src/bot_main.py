import json

import discord
from discord import app_commands
from event.on_ready import on_ready as on_ready_event
from event.on_message import on_message as on_message_event
from event.on_reaction import on_reaction as on_reaction_event
from event.on_member_join import on_member_join as on_member_join_event
from event.on_voice_state_update import on_voice_state_update as on_voice_state_update_event
from event.on_message.command.slash_commands import register_slash_commands
from function.file.path_service import application_root
from function.security.single_instance import single_instance


#----------Botの設定はここ----------
#Botの設定を読み込み
PROJECT_ROOT = application_root()
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"

with CONFIG_PATH.open(encoding='utf-8-sig') as f:
    config = json.load(f)
TOKEN = config['BOT_TOKEN']
# 接続に必要なオブジェクトを生成
intents_set = discord.Intents.default() 
intents_set.message_content = True      #メッセージの内容を取得するために必要
intents_set.reactions = True            #リアクションを取得するために必要
intents_set.members = True              #メンバー情報を取得するために必要
intents_set.voice_states = True         #ボイスチャンネルの状態を取得するために必要
client = discord.Client(intents=intents_set)
command_tree = app_commands.CommandTree(client)
register_slash_commands(command_tree)
commands_synced = False

#----------イベントハンドラ群はここ----------
"""Bot起動時に実行されるイベントハンドラ"""
@client.event
async def on_ready() -> None:
    global commands_synced
    if not commands_synced:
        await command_tree.sync()
        commands_synced = True
    await on_ready_event.on_ready_main(client)

"""メッセージ受信時に実行されるイベントハンドラ"""
@client.event
async def on_message(message: discord.Message) -> None:
    await on_message_event.on_message_main(client, message)

"""リアクション追加時に実行されるイベントハンドラ"""
@client.event
async def on_reaction_add(
    reaction: discord.Reaction,
    user: discord.User,
) -> None:
    await on_reaction_event.on_reaction_main(client, reaction, user)

"""新規メンバー参加時に実行されるイベントハンドラ"""
@client.event
async def on_member_join(member: discord.Member) -> None:
    await on_member_join_event.on_member_join_main(client, member)

"""メンバーのボイスチャンネル出入り時に実行されるイベントハンドラ"""
@client.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    await on_voice_state_update_event.on_voice_state_update_main(
        client,
        member,
        before,
        after,
    )

#----------Botの起動処理はここ----------
# Botの起動とDiscordサーバーへの接続
with single_instance(r"Local\DiscordBot_servercontroller") as is_primary:
    if not is_primary:
        print("BOTはすでに起動しているため、このプロセスを終了します。")
        raise SystemExit(0)
    client.run(TOKEN)