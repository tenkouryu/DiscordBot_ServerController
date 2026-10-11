from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import discord

from function.file.template_output_service import save_template_output, send_template_output
from function.security.permissions import can_manage_channels, can_manage_roles


def _role_data(role: discord.Role) -> dict[str, Any]:
    return {
        "id": str(role.id),
        "name": role.name,
        "color": f"#{role.color.value:06X}",
        "position": role.position,
        "is_default": role.is_default(),
        "managed": role.managed,
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "permissions": {
            name: getattr(role.permissions, name)
            for name in sorted(discord.Permissions.VALID_FLAGS)
        },
    }


def _member_data(member: discord.Member) -> dict[str, Any]:
    return {
        "id": str(member.id),
        "name": member.name,
        "display_name": member.display_name,
        "bot": member.bot,
        "role_ids": [str(role.id) for role in member.roles],
    }


def _overwrite_data(
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite],
) -> list[dict[str, Any]]:
    serialized = []
    for target, overwrite in overwrites.items():
        allow, deny = overwrite.pair()
        serialized.append(
            {
                "target_type": "role" if isinstance(target, discord.Role) else "member",
                "target_id": str(target.id),
                "target_name": target.name,
                "allow": sorted(
                    name
                    for name in discord.Permissions.VALID_FLAGS
                    if getattr(allow, name)
                ),
                "deny": sorted(
                    name
                    for name in discord.Permissions.VALID_FLAGS
                    if getattr(deny, name)
                ),
            }
        )
    return sorted(serialized, key=lambda item: (item["target_type"], item["target_id"]))


def _channel_data(channel: discord.abc.GuildChannel) -> dict[str, Any]:
    channel_type = channel.type.name
    result: dict[str, Any] = {
        "id": str(channel.id),
        "name": channel.name,
        "type": channel_type,
        "position": channel.position,
        "category_id": str(channel.category_id) if channel.category_id is not None else None,
        "category_name": channel.category.name if channel.category is not None else None,
        "permission_overwrites": _overwrite_data(channel.overwrites),
    }
    if isinstance(channel, discord.TextChannel):
        result.update(
            topic=channel.topic,
            nsfw=channel.nsfw,
            slowmode_seconds=channel.slowmode_delay,
        )
    elif isinstance(channel, discord.VoiceChannel):
        result.update(
            bitrate=channel.bitrate,
            user_limit=channel.user_limit,
            rtc_region=channel.rtc_region,
            video_quality_mode=channel.video_quality_mode.name,
        )
    elif isinstance(channel, discord.CategoryChannel):
        result["nsfw"] = channel.nsfw
    elif isinstance(channel, discord.StageChannel):
        result.update(
            bitrate=channel.bitrate,
            user_limit=channel.user_limit,
            rtc_region=channel.rtc_region,
            video_quality_mode=channel.video_quality_mode.name,
        )
    elif isinstance(channel, discord.ForumChannel):
        result.update(
            topic=channel.topic,
            nsfw=channel.nsfw,
            slowmode_seconds=channel.slowmode_delay,
            default_auto_archive_duration=channel.default_auto_archive_duration,
            default_thread_slowmode_seconds=channel.default_thread_slowmode_delay,
            default_sort_order=(
                channel.default_sort_order.name
                if channel.default_sort_order is not None
                else None
            ),
            default_layout=channel.default_layout.name,
            available_tags=[
                {
                    "id": str(tag.id),
                    "name": tag.name,
                    "moderated": tag.moderated,
                    "emoji": str(tag.emoji) if tag.emoji else None,
                }
                for tag in channel.available_tags
            ],
        )
    return result


def build_server_export(guild: discord.Guild) -> dict[str, Any]:
    """Build one JSON-serializable snapshot of roles, member roles, and channels."""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    return {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "guild": {
            "id": str(guild.id),
            "name": guild.name,
            "owner_id": str(guild.owner_id) if guild.owner_id is not None else None,
        },
        "roles": [
            _role_data(role)
            for role in sorted(guild.roles, key=lambda item: (item.position, item.id))
        ],
        "members": [
            _member_data(member)
            for member in sorted(guild.members, key=lambda item: item.id)
        ],
        "channels": [
            _channel_data(channel)
            for channel in sorted(guild.channels, key=lambda item: (item.position, item.id))
        ],
    }


def export_server_to_json(guild: discord.Guild) -> bytes:
    """Serialize the server configuration snapshot as UTF-8 JSON."""
    return json.dumps(
        build_server_export(guild),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


async def main(message: discord.Message) -> None:
    if message.guild is None:
        await message.channel.send("このコマンドはサーバー内で実行してください。")
        return
    if not can_manage_roles(message.author) or not can_manage_channels(message.author):
        await message.channel.send(
            "サーバー情報のJSON取得には、ロール管理権限とチャンネル管理権限の両方が必要です。"
        )
        return

    result_path = save_template_output(
        "get/result",
        f"server_export_{message.guild.id}",
        export_server_to_json(message.guild),
        suffix=".json",
    )
    await send_template_output(
        message.channel,
        "サーバーロール、メンバーロール、チャンネル情報をJSONで送信します。",
        result_path,
    )
