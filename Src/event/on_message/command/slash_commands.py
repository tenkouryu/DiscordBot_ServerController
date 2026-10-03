from __future__ import annotations

from typing import Any

import discord
from discord import app_commands

from .channel import create as channel_create
from .channel import get as channel_get
from .channel import move as channel_move
from .channel import set as channel_set
from .channel import template as channel_template
from .chat import get as chat_get
from .chat import template as chat_template
from .help.help import get_command_help_text
from .member import role_add as member_role_add
from .member import role_get as member_role_get
from .member import role_remove as member_role_remove
from .member import role_set as member_role_set
from .member import role_template as member_role_template
from .member import role_update as member_role_update
from .scenario import delete as scenario_delete
from .scenario import export as scenario_export
from .scenario import list as scenario_list
from .scenario import set as scenario_set
from .scenario import start as scenario_start
from .scenario import template as scenario_template
from .server import member_list as server_member_list
from .server import role_add as server_role_add
from .server import role_edit as server_role_edit
from .server import role_get as server_role_get
from .server import role_permissions as server_role_permissions
from .server import role_remove as server_role_remove
from .server import role_set as server_role_set
from .server import role_template as server_role_template


class _InteractionChannel:
    """interaction の応答を legacy handler の channel.send 互換で扱う。"""

    def __init__(self, interaction: discord.Interaction) -> None:
        self._interaction = interaction

    def __getattr__(self, name: str) -> Any:
        channel = self._interaction.channel
        if channel is None:
            raise AttributeError(name)
        return getattr(channel, name)

    async def send(self, *args: Any, **kwargs: Any) -> Any:
        if self._interaction.response.is_done():
            kwargs.setdefault("wait", True)
            return await self._interaction.followup.send(*args, **kwargs)
        return await self._interaction.response.send_message(*args, **kwargs)


class _InteractionMessage:
    """既存メッセージコマンドへInteractionを渡すアダプター。"""

    def __init__(
        self,
        interaction: discord.Interaction,
        content: str,
        *,
        attachments: list[discord.Attachment] | None = None,
        mentions: list[discord.User] | None = None,
        channel_mentions: list[discord.abc.GuildChannel] | None = None,
    ) -> None:
        self._interaction = interaction
        self.content = content
        self.attachments = attachments or []
        self.mentions = mentions or []
        self.channel_mentions = channel_mentions or []
        self.channel = _InteractionChannel(interaction)

    @property
    def author(self) -> discord.User | discord.Member:
        return self._interaction.user

    def __getattr__(self, name: str) -> Any:
        return getattr(self._interaction, name)


async def _run(
    interaction: discord.Interaction,
    handler: Any,
    content: str,
    *,
    attachments: list[discord.Attachment] | None = None,
    mentions: list[discord.User] | None = None,
    channel_mentions: list[discord.abc.GuildChannel] | None = None,
) -> None:
    try:
        await interaction.response.defer()
    except discord.NotFound:
        # Discord interaction tokens expire quickly; there is no response to send after that.
        return
    await handler(
        _InteractionMessage(
            interaction,
            content,
            attachments=attachments,
            mentions=mentions,
            channel_mentions=channel_mentions,
        )
    )


def register_slash_commands(tree: app_commands.CommandTree[discord.Client]) -> None:
    """既存コマンドをDiscordのスラッシュコマンドとして登録する。"""
    member_group = app_commands.Group(name="member", description="メンバー操作")
    member_role = app_commands.Group(name="role", description="メンバーのロール操作", parent=member_group)
    server_group = app_commands.Group(name="server", description="サーバー操作")
    server_role = app_commands.Group(name="role", description="サーバーのロール操作", parent=server_group)
    server_member = app_commands.Group(name="member", description="サーバーメンバー操作", parent=server_group)
    channel_group = app_commands.Group(name="channel", description="チャンネル操作")
    chat_group = app_commands.Group(name="chat", description="添付ファイル操作")
    scenario_group = app_commands.Group(name="scenario", description="シナリオ操作")

    @tree.command(name="help", description="利用可能なコマンドを表示")
    async def help_command(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(get_command_help_text())

    @member_role.command(name="add", description="メンバーにロールを追加")
    @app_commands.describe(member="対象メンバー", role_name="ロール名")
    async def member_role_add_command(interaction: discord.Interaction, member: discord.Member, role_name: str) -> None:
        await _run(interaction, member_role_add.main, f"/member_role_add {member.mention} {role_name}", mentions=[member])

    @member_role.command(name="get", description="メンバーのロール一覧を表示")
    async def member_role_get_command(interaction: discord.Interaction, username: str) -> None:
        await _run(interaction, member_role_get.main, f"/member_role_get {username}")

    @member_role.command(name="remove", description="メンバーからロールを削除")
    async def member_role_remove_command(interaction: discord.Interaction, member: discord.Member, role_name: str) -> None:
        await _run(interaction, member_role_remove.main, f"/member_role_remove {member.mention} {role_name}", mentions=[member])

    @member_role.command(name="set", description="CSVからメンバーロールを設定")
    async def member_role_set_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
        await _run(interaction, member_role_set.main, "/member_role_set", attachments=[file])

    @member_role.command(name="template", description="メンバーロールCSVテンプレート")
    async def member_role_template_command(interaction: discord.Interaction) -> None:
        await _run(interaction, member_role_template.main, "/member_role_template")

    @member_role.command(name="update", description="メンバー一覧CSVからロールを更新")
    async def member_role_update_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
        await _run(interaction, member_role_update.main, "/member_role_update", attachments=[file])

    @server_role.command(name="add", description="サーバーにロールを追加")
    async def server_role_add_command(interaction: discord.Interaction, role_name: str) -> None:
        await _run(interaction, server_role_add.main, f"/server_role_add {role_name}")

    @server_role.command(name="edit", description="ロールの権限または色を変更")
    async def server_role_edit_command(interaction: discord.Interaction, role_name: str, setting: str, value: str) -> None:
        await _run(interaction, server_role_edit.main, f"/server_role_edit {role_name} {setting} {value}")

    @server_role.command(name="permissions", description="ロール権限名と説明をCSVで取得")
    async def server_role_permissions_command(interaction: discord.Interaction) -> None:
        await _run(interaction, server_role_permissions.main, "/server_role_permissions")

    @server_role.command(name="get", description="サーバーロールをCSVで取得")
    async def server_role_get_command(interaction: discord.Interaction) -> None:
        await _run(interaction, server_role_get.main, "/server_role_get")

    @server_role.command(name="set", description="CSVからサーバーロールを設定")
    async def server_role_set_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
        await _run(interaction, server_role_set.main, "/server_role_set", attachments=[file])

    @server_role.command(name="template", description="サーバーロールCSVテンプレート")
    async def server_role_template_command(interaction: discord.Interaction) -> None:
        await _run(interaction, server_role_template.main, "/server_role_template")

    @server_role.command(name="remove", description="サーバーからロールを削除")
    async def server_role_remove_command(interaction: discord.Interaction, role_name: str) -> None:
        await _run(interaction, server_role_remove.main, f"/server_role_remove {role_name}")

    @server_member.command(name="list", description="サーバーメンバー一覧をCSVで取得")
    async def server_member_list_command(interaction: discord.Interaction) -> None:
        await _run(interaction, lambda message: server_member_list.main(interaction.client, message), "/server_member_list")

    @channel_group.command(name="create", description="チャンネルを作成")
    async def channel_create_command(interaction: discord.Interaction, channel_type: str, channel_name: str, category_name: str | None = None) -> None:
        await _run(interaction, channel_create.main, f"/channel_create {channel_type} {channel_name} {category_name or ''}")

    @channel_group.command(name="get", description="チャンネル一覧をCSVで取得")
    async def channel_get_command(interaction: discord.Interaction) -> None:
        await _run(interaction, channel_get.main, "/channel_get")

    @channel_group.command(name="move", description="チャンネルをカテゴリーへ移動")
    async def channel_move_command(interaction: discord.Interaction, channel: discord.TextChannel, category_name: str) -> None:
        await _run(interaction, channel_move.main, f"/channel_move {channel.mention} {category_name}", channel_mentions=[channel])

    @channel_group.command(name="set", description="CSVからチャンネルを設定")
    async def channel_set_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
        await _run(interaction, channel_set.main, "/channel_set", attachments=[file])

    @channel_group.command(name="template", description="チャンネルCSVテンプレート")
    async def channel_template_command(interaction: discord.Interaction) -> None:
        await _run(interaction, channel_template.main, "/channel_template")

    @chat_group.command(name="get", description="添付ファイルを取得")
    async def chat_get_command(interaction: discord.Interaction, channel: discord.TextChannel, start_date: str | None = None, extension: str | None = None) -> None:
        arguments = " ".join(value for value in (start_date, extension) if value)
        await _run(interaction, chat_get.main, f"/chat_get {arguments}", channel_mentions=[channel])

    @chat_group.command(name="template", description="添付ファイル取得CSVテンプレート")
    async def chat_template_command(interaction: discord.Interaction) -> None:
        await _run(interaction, chat_template.main, "/chat_template")

    @scenario_group.command(name="template", description="シナリオCSVテンプレート")
    async def scenario_template_command(interaction: discord.Interaction) -> None:
        await _run(interaction, scenario_template.main, "/scenario_template")

    @scenario_group.command(name="set", description="CSVからシナリオを登録")
    async def scenario_set_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
        await _run(interaction, scenario_set.main, "/scenario_set", attachments=[file])

    @scenario_group.command(name="list", description="登録済みシナリオ一覧")
    async def scenario_list_command(interaction: discord.Interaction) -> None:
        await _run(interaction, scenario_list.main, "/scenario_list")

    @scenario_group.command(name="start", description="シナリオを開始")
    async def scenario_start_command(interaction: discord.Interaction, scenario_id: str, start_step: int | None = None) -> None:
        content = f"/scenario_start {scenario_id} {start_step or ''}"
        await _run(interaction, scenario_start.main, content)

    @scenario_group.command(name="delete", description="シナリオを削除")
    async def scenario_delete_command(interaction: discord.Interaction, scenario_id: str) -> None:
        await _run(interaction, scenario_delete.main, f"/scenario_delete {scenario_id}")

    @scenario_group.command(name="export", description="シナリオをCSVで出力")
    async def scenario_export_command(interaction: discord.Interaction) -> None:
        await _run(interaction, scenario_export.main, "/scenario_export")

    tree.add_command(member_group)
    tree.add_command(server_group)
    tree.add_command(channel_group)
    tree.add_command(chat_group)
    tree.add_command(scenario_group)
