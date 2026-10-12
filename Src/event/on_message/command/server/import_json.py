from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any

import discord

from event.on_message.command.server.export_json import export_server_to_json
from function.file.template_output_service import save_template_output, send_template_output
from function.security.permissions import can_manage_channels, can_manage_roles


def parse_server_export(payload: bytes) -> dict[str, Any]:
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"JSONを読み込めませんでした: {error}") from error
    if (
        not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document["schema_version"] != 1
    ):
        raise ValueError("対応しているサーバーJSON形式ではありません。")
    if not isinstance(document.get("guild"), dict):
        raise ValueError("guild オブジェクトがありません。")
    for field in ("roles", "members", "channels"):
        if not isinstance(document.get(field), list):
            raise ValueError(f"{field} は配列で指定してください。")
        if not all(isinstance(item, dict) for item in document[field]):
            raise ValueError(f"{field} の要素はすべてオブジェクトで指定してください。")

    role_ids: set[str] = set()
    role_names: set[str] = set()
    default_role_count = 0
    valid_permissions = set(discord.Permissions.VALID_FLAGS)
    for role in document["roles"]:
        role_id = _required_string(role, "id", "roles")
        role_name = _required_string(role, "name", "roles")
        if role_id in role_ids:
            raise ValueError(f"roles に重複した id があります: {role_id}")
        if role_name in role_names:
            raise ValueError(f"roles に重複した name があります: {role_name}")
        role_ids.add(role_id)
        role_names.add(role_name)
        permissions = role.get("permissions")
        if not isinstance(permissions, dict):
            raise ValueError(f"ロール「{role_name}」の permissions が不正です。")
        unknown = set(permissions) - valid_permissions
        if unknown:
            raise ValueError(
                f"ロール「{role_name}」に未対応の権限があります: {', '.join(sorted(unknown))}"
            )
        if not all(isinstance(value, bool) for value in permissions.values()):
            raise ValueError(f"ロール「{role_name}」の権限値は true/false で指定してください。")
        color = role.get("color")
        if not isinstance(color, str) or len(color.lstrip("#")) != 6:
            raise ValueError(f"ロール「{role_name}」の color が不正です。")
        try:
            int(color.lstrip("#"), 16)
        except ValueError as error:
            raise ValueError(f"ロール「{role_name}」の color が不正です。") from error
        if not isinstance(role.get("is_default"), bool):
            raise ValueError(f"ロール「{role_name}」の is_default が不正です。")
        default_role_count += role["is_default"]
    if default_role_count > 1:
        raise ValueError("roles に @everyone ロールが複数あります。")
    if default_role_count != 1:
        raise ValueError("roles に @everyone ロールを1件含めてください。")

    member_ids: set[str] = set()
    for member in document["members"]:
        member_id = _required_string(member, "id", "members")
        _required_string(member, "name", "members")
        role_list = member.get("role_ids")
        if not isinstance(role_list, list) or not all(isinstance(value, str) for value in role_list):
            raise ValueError(f"メンバー「{member['name']}」の role_ids が不正です。")
        if member_id in member_ids:
            raise ValueError(f"members に重複した id があります: {member_id}")
        member_ids.add(member_id)
        unknown_role_ids = set(role_list) - role_ids
        if unknown_role_ids:
            raise ValueError(
                f"メンバー「{member['name']}」に未定義のロールIDがあります: "
                f"{', '.join(sorted(unknown_role_ids))}"
            )

    channel_ids: set[str] = set()
    supported_channel_types = {"category", "text", "news", "voice", "stage_voice", "forum"}
    for channel in document["channels"]:
        channel_id = _required_string(channel, "id", "channels")
        _required_string(channel, "name", "channels")
        _required_string(channel, "type", "channels")
        if channel_id in channel_ids:
            raise ValueError(f"channels に重複した id があります: {channel_id}")
        channel_ids.add(channel_id)
        if channel["type"] not in supported_channel_types:
            raise ValueError(
                f"チャンネル「{channel['name']}」の種別には対応していません: {channel['type']}"
            )
        if not isinstance(channel.get("position"), int):
            raise ValueError(f"チャンネル「{channel['name']}」の position が不正です。")
        if channel.get("category_name") is not None and not isinstance(
            channel["category_name"], str
        ):
            raise ValueError(f"チャンネル「{channel['name']}」の category_name が不正です。")
        overwrites = channel.get("permission_overwrites")
        if not isinstance(overwrites, list) or not all(isinstance(item, dict) for item in overwrites):
            raise ValueError(f"チャンネル「{channel['name']}」の permission_overwrites が不正です。")
        for overwrite in overwrites:
            if overwrite.get("target_type") not in {"role", "member"}:
                raise ValueError(f"チャンネル「{channel['name']}」の権限対象が不正です。")
            target_id = _required_string(
                overwrite,
                "target_id",
                f"channels/{channel['name']}/permission_overwrites",
            )
            if not isinstance(overwrite.get("target_name"), str):
                raise ValueError(f"チャンネル「{channel['name']}」の権限対象名が不正です。")
            reference_ids = role_ids if overwrite["target_type"] == "role" else member_ids
            if target_id not in reference_ids:
                raise ValueError(f"チャンネル「{channel['name']}」の権限対象IDがJSONにありません。")
            for field in ("allow", "deny"):
                values = overwrite.get(field)
                if not isinstance(values, list) or not all(
                    isinstance(value, str) and value in valid_permissions for value in values
                ):
                    raise ValueError(f"チャンネル「{channel['name']}」の {field} 権限が不正です。")
            if set(overwrite["allow"]) & set(overwrite["deny"]):
                raise ValueError(f"チャンネル「{channel['name']}」の権限が競合しています。")
    return document


def _required_string(item: dict[str, Any], field: str, section: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{section} の {field} は空でない文字列が必要です。")
    return value.strip()


def _unique_named(items: list[Any], name: str, *, attribute: str = "name") -> Any | None:
    matches = [
        item for item in items
        if getattr(item, attribute, "").casefold() == name.casefold()
    ]
    if len(matches) > 1:
        raise ValueError(f"名前が重複しているため対応付けできません: {name}")
    return matches[0] if matches else None


def _source_name_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _result_row(
    section: str,
    name: str,
    action: str,
    result: str,
    reason: str = "",
) -> dict[str, str]:
    return {
        "対象種別": section,
        "名前": name,
        "処理": action,
        "result": result,
        "reason": reason,
    }


def build_import_result_csv(results: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = ("対象種別", "名前", "処理", "result", "reason")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(results)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _resolve_member(guild: discord.Guild, source: dict[str, Any]) -> discord.Member:
    member = _unique_named(list(guild.members), source["name"])
    if member is None and source.get("display_name"):
        member = _unique_named(
            list(guild.members),
            source["display_name"],
            attribute="display_name",
        )
    if member is None:
        raise ValueError(f"メンバーが見つかりません: {source['name']}")
    return member


def _resolve_overwrite_target(
    guild: discord.Guild,
    overwrite: dict[str, Any],
    roles_by_source_id: dict[str, dict[str, Any]],
    members_by_source_id: dict[str, dict[str, Any]],
) -> discord.Role | discord.Member:
    if overwrite["target_type"] == "role":
        source_role = roles_by_source_id.get(overwrite["target_id"])
        if source_role is None:
            raise ValueError(f"JSON内に権限対象ロールがありません: {overwrite['target_id']}")
        if source_role.get("is_default"):
            return guild.default_role
        role = _unique_named(list(guild.roles), source_role["name"])
        if role is None:
            raise ValueError(f"権限対象ロールが見つかりません: {source_role['name']}")
        return role

    source_member = members_by_source_id.get(overwrite["target_id"])
    if source_member is None:
        raise ValueError(f"JSON内に権限対象メンバーがありません: {overwrite['target_id']}")
    return _resolve_member(guild, source_member)


async def apply_server_export(
    document: dict[str, Any],
    guild: discord.Guild,
) -> dict[str, Any]:
    """Synchronize manageable roles, member roles, and channels with the snapshot."""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")
    document = parse_server_export(
        json.dumps(document, ensure_ascii=False).encode("utf-8")
    )
    counts = Counter()
    errors: list[str] = []
    results: list[dict[str, str]] = []
    source_roles = _source_name_map(document["roles"])
    source_members = _source_name_map(document["members"])

    target_roles: dict[str, discord.Role] = {}
    default_source_id = None
    for source in document["roles"]:
        action = "更新"
        try:
            if source.get("is_default"):
                await guild.default_role.edit(
                    permissions=discord.Permissions(**source["permissions"])
                )
                target_roles[source["id"]] = guild.default_role
                default_source_id = source["id"]
                counts["roles_updated"] += 1
                results.append(_result_row("ロール", source["name"], "更新", "成功"))
                continue
            role = _unique_named(list(guild.roles), source["name"])
            if role is not None and role.managed:
                reason = "Botまたは連携サービスが管理しているため変更できません。"
                target_roles[source["id"]] = role
                counts["roles_skipped"] += 1
                errors.append(f"ロール {source['name']}: {reason}")
                results.append(_result_row("ロール", source["name"], "スキップ", "一部成功", reason))
                continue
            permissions = discord.Permissions(**source["permissions"])
            color_value = int(source["color"].lstrip("#"), 16)
            if not 0 <= color_value <= 0xFFFFFF:
                raise ValueError(f"ロール「{source['name']}」の色が不正です。")
            color = discord.Colour(color_value)
            if role is None:
                action = "作成"
                role = await guild.create_role(
                    name=source["name"],
                    permissions=permissions,
                    colour=color,
                    hoist=bool(source.get("hoist", False)),
                    mentionable=bool(source.get("mentionable", False)),
                )
                counts["roles_created"] += 1
                action = "作成"
            else:
                await role.edit(
                    name=source["name"],
                    permissions=permissions,
                    colour=color,
                    hoist=bool(source.get("hoist", False)),
                    mentionable=bool(source.get("mentionable", False)),
                )
                counts["roles_updated"] += 1
                action = "更新"
            target_roles[source["id"]] = role
            results.append(_result_row("ロール", source["name"], action, "成功"))
        except (ValueError, discord.Forbidden, discord.HTTPException) as error:
            counts["roles_failed"] += 1
            errors.append(f"ロール {source['name']}: {error}")
            results.append(_result_row("ロール", source["name"], action, "失敗", str(error)))
    positions = {
        role: source["position"]
        for source in document["roles"]
        if not source.get("is_default")
        and source["id"] in target_roles
        and isinstance(source.get("position"), int)
    }
    if positions:
        try:
            await guild.edit_role_positions(positions=positions)
        except (discord.Forbidden, discord.HTTPException) as error:
            reason = f"ロール位置を反映できませんでした: {error}"
            errors.append(reason)
            positioned_role_names = {
                source["name"]
                for source in document["roles"]
                if (
                    not source.get("is_default")
                    and source["id"] in target_roles
                    and isinstance(source.get("position"), int)
                )
            }
            for result in results:
                if (
                    result["対象種別"] == "ロール"
                    and result["名前"] in positioned_role_names
                    and result["result"] == "成功"
                ):
                    result["result"] = "一部成功"
                    result["reason"] = reason

    matched_member_ids: set[int] = set()
    for source in document["members"]:
        try:
            member = _resolve_member(guild, source)
            matched_member_ids.add(member.id)
            unmapped_role_ids = set(source["role_ids"]) - set(target_roles)
            if unmapped_role_ids:
                role_names = [
                    source_roles[role_id]["name"]
                    for role_id in sorted(unmapped_role_ids)
                ]
                raise ValueError(
                    f"ロールを適用できないため処理をスキップしました: {', '.join(role_names)}"
                )
            desired_roles = {
                target_roles[role_id]
                for role_id in source["role_ids"]
                if role_id in target_roles and role_id != default_source_id
            }
            current_roles = set(member.roles)
            to_add = desired_roles - set(member.roles)
            to_remove = {
                role
                for role in current_roles - desired_roles
                if role != guild.default_role and not role.managed
            }
            to_add = {role for role in to_add if not role.managed}
            managed_mismatches = {
                role
                for role in current_roles ^ desired_roles
                if role.managed
            }
            if to_add:
                await member.add_roles(*to_add)
            if to_remove:
                await member.remove_roles(*to_remove)
            counts["members_updated"] += 1
            if managed_mismatches:
                reason = "管理ロールはBotが変更できないため、割り当てを完全一致できません。"
                errors.append(f"メンバー {source['name']}: {reason}")
                results.append(
                    _result_row("メンバー", source["name"], "ロール更新", "一部成功", reason)
                )
            else:
                results.append(_result_row("メンバー", source["name"], "ロール更新", "成功"))
        except (ValueError, discord.Forbidden, discord.HTTPException) as error:
            counts["members_skipped"] += 1
            errors.append(f"メンバー {source['name']}: {error}")
            results.append(_result_row("メンバー", source["name"], "ロール更新", "失敗", str(error)))

    for member in guild.members:
        if member.id in matched_member_ids:
            continue
        try:
            to_remove = [
                role
                for role in member.roles
                if role != guild.default_role and not role.managed
            ]
            if to_remove:
                await member.remove_roles(*to_remove)
            counts["members_updated"] += 1
            managed_roles = [role for role in member.roles if role.managed]
            if managed_roles:
                reason = "JSONにないメンバーの管理ロールはBotが変更できないため保持しました。"
                errors.append(f"メンバー {member.name}: {reason}")
                results.append(
                    _result_row("メンバー", member.name, "JSON対象外ロール削除", "一部成功", reason)
                )
            else:
                results.append(
                    _result_row("メンバー", member.name, "JSON対象外ロール削除", "成功")
                )
        except (discord.Forbidden, discord.HTTPException) as error:
            counts["members_skipped"] += 1
            errors.append(f"メンバー {member.name}: {error}")
            results.append(
                _result_row("メンバー", member.name, "JSON対象外ロール削除", "失敗", str(error))
            )

    source_channels = sorted(
        document["channels"],
        key=lambda item: (item["type"] != "category", item.get("position", 0), item["name"].casefold()),
    )
    target_channels: dict[str, discord.abc.GuildChannel] = {}
    for source in source_channels:
        try:
            target, created, warnings = await _apply_channel(
                guild,
                source,
                target_channels,
                source_roles,
                source_members,
            )
            target_channels[source["id"]] = target
            counts["channels_created" if created else "channels_updated"] += 1
            result = "一部成功" if warnings else "成功"
            reason = "; ".join(warnings)
            results.append(
                _result_row(
                    "チャンネル",
                    source["name"],
                    "作成" if created else "更新",
                    result,
                    reason,
                )
            )
            errors.extend(
                f"チャンネル {source['name']}: {warning}" for warning in warnings
            )
        except (ValueError, discord.Forbidden, discord.HTTPException, TypeError) as error:
            counts["channels_skipped"] += 1
            errors.append(f"チャンネル {source['name']}: {error}")
            results.append(_result_row("チャンネル", source["name"], "スキップ", "失敗", str(error)))

    source_channel_keys = {
        (item["type"], item["name"].casefold())
        for item in document["channels"]
    }
    source_channel_keys.update(
        ("category", item["category_name"].casefold())
        for item in document["channels"]
        if item.get("category_name")
    )
    extra_channels = sorted(
        (
            channel for channel in list(guild.channels)
            if (channel.type.name, channel.name.casefold()) not in source_channel_keys
        ),
        key=lambda channel: channel.type.name == "category",
    )
    for channel in extra_channels:
        try:
            await channel.delete(reason="server import JSON synchronization")
            counts["channels_deleted"] += 1
            results.append(_result_row("チャンネル", channel.name, "削除", "成功"))
        except (discord.Forbidden, discord.HTTPException) as error:
            counts["channels_skipped"] += 1
            errors.append(f"チャンネル {channel.name}: {error}")
            results.append(_result_row("チャンネル", channel.name, "削除", "失敗", str(error)))

    source_role_names = {role["name"].casefold() for role in document["roles"]}
    for role in list(guild.roles):
        if role == guild.default_role or role.managed or role.name.casefold() in source_role_names:
            continue
        try:
            await role.delete(reason="server import JSON synchronization")
            counts["roles_deleted"] += 1
            results.append(_result_row("ロール", role.name, "削除", "成功"))
        except (discord.Forbidden, discord.HTTPException) as error:
            counts["roles_failed"] += 1
            errors.append(f"ロール {role.name}: {error}")
            results.append(_result_row("ロール", role.name, "削除", "失敗", str(error)))

    for role in list(guild.roles):
        if (
            role != guild.default_role
            and role.managed
            and role.name.casefold() not in source_role_names
        ):
            reason = "Botまたは連携サービスが管理しているため削除できません。"
            counts["roles_skipped"] += 1
            errors.append(f"ロール {role.name}: {reason}")
            results.append(_result_row("ロール", role.name, "削除", "一部成功", reason))
    counts["errors"] = errors
    counts["results"] = results
    return dict(counts)


async def _apply_channel(
    guild: discord.Guild,
    source: dict[str, Any],
    created_by_name: dict[str, discord.abc.GuildChannel],
    source_roles: dict[str, dict[str, Any]],
    source_members: dict[str, dict[str, Any]],
) -> tuple[discord.abc.GuildChannel, bool, list[str]]:
    channel_type = source["type"]
    name = source["name"]
    existing = created_by_name.get(f"{channel_type}:{name.casefold()}")
    if existing is None:
        candidates = [
            channel for channel in guild.channels
            if channel.type.name == channel_type
            and channel.name.casefold() == name.casefold()
        ]
        if len(candidates) > 1:
            raise ValueError(f"同名チャンネルが複数あるため対応付けできません: {name}")
        existing = candidates[0] if candidates else None

    category_name = source.get("category_name")
    category = None
    if category_name:
        category_source = _unique_named(
            [
                item for item in guild.channels
                if isinstance(item, discord.CategoryChannel)
            ],
            category_name,
        )
        category = category_source
        if category is None:
            category = created_by_name.get(f"category:{category_name.casefold()}")
        if category is None:
            category = await guild.create_category(category_name)
            created_by_name[f"category:{category_name.casefold()}"] = category

    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}
    warnings: list[str] = []
    for item in source["permission_overwrites"]:
        try:
            target = _resolve_overwrite_target(
                guild,
                item,
                source_roles,
                source_members,
            )
        except ValueError as error:
            warnings.append(str(error))
            continue
        overwrites[target] = discord.PermissionOverwrite.from_pair(
            discord.Permissions(**dict.fromkeys(item["allow"], True)),
            discord.Permissions(**dict.fromkeys(item["deny"], True)),
        )
    kwargs: dict[str, Any] = {
        "name": name,
        "position": source.get("position", 0),
        "overwrites": overwrites,
    }
    if channel_type != "category":
        kwargs["category"] = category

    if channel_type == "category":
        create = guild.create_category
        kwargs["nsfw"] = bool(source.get("nsfw", False))
        kwargs.pop("overwrites", None)
        kwargs.pop("position", None)
        kwargs["overwrites"] = overwrites
        kwargs["position"] = source.get("position", 0)
    elif channel_type in {"text", "news"}:
        kwargs.update(
            topic=source.get("topic"),
            nsfw=bool(source.get("nsfw", False)),
            slowmode_delay=source.get("slowmode_seconds", 0),
        )
        if channel_type == "news":
            kwargs["news"] = True
        create = guild.create_text_channel
    elif channel_type == "voice":
        kwargs.update(
            bitrate=source.get("bitrate", 64000),
            user_limit=source.get("user_limit", 0),
            rtc_region=source.get("rtc_region"),
            video_quality_mode=discord.VideoQualityMode[
                source.get("video_quality_mode", "auto")
            ],
        )
        create = guild.create_voice_channel
    elif channel_type == "stage_voice":
        kwargs.update(
            bitrate=source.get("bitrate", 64000),
            user_limit=source.get("user_limit", 0),
            rtc_region=source.get("rtc_region"),
            video_quality_mode=discord.VideoQualityMode[
                source.get("video_quality_mode", "auto")
            ],
        )
        create = guild.create_stage_channel
    elif channel_type == "forum":
        kwargs.update(
            topic=source.get("topic"),
            nsfw=bool(source.get("nsfw", False)),
            slowmode_delay=source.get("slowmode_seconds", 0),
            default_auto_archive_duration=source.get("default_auto_archive_duration", 1440),
            default_thread_slowmode_delay=source.get("default_thread_slowmode_seconds", 0),
            default_layout=discord.ForumLayoutType[
                source.get("default_layout", "not_set")
            ],
            available_tags=[
                discord.ForumTag(
                    name=tag["name"],
                    moderated=tag.get("moderated", False),
                    emoji=tag.get("emoji"),
                )
                for tag in source.get("available_tags", [])
            ],
        )
        if source.get("default_sort_order"):
            kwargs["default_sort_order"] = discord.ForumOrderType[
                source["default_sort_order"]
            ]
        create = guild.create_forum
    else:
        raise ValueError(f"未対応のチャンネル種別です: {channel_type}")

    if existing is None:
        category_nsfw = kwargs.pop("nsfw", False) if channel_type == "category" else False
        if channel_type == "news":
            kwargs.pop("news", None)
        channel = await create(**kwargs)
        if channel_type == "category":
            channel = await channel.edit(nsfw=category_nsfw) or channel
    else:
        if channel_type == "news":
            kwargs.pop("news", None)
        channel = await existing.edit(**kwargs) or existing
    created_by_name[f"{channel_type}:{name.casefold()}"] = channel
    if channel_type == "category":
        created_by_name[f"category:{name.casefold()}"] = channel
    return channel, existing is None, warnings


async def main(message: discord.Message) -> None:
    if message.guild is None:
        await message.channel.send("このコマンドはサーバー内で実行してください。")
        return
    if not can_manage_roles(message.author) or not can_manage_channels(message.author):
        await message.channel.send(
            "サーバー設定のJSON適用には、ロール管理権限とチャンネル管理権限の両方が必要です。"
        )
        return
    attachment = next(
        (
            item for item in message.attachments
            if item.filename.lower().endswith(".json")
        ),
        None,
    )
    if attachment is None:
        await message.channel.send("エクスポートJSONファイルを添付してください。使い方: /server import + JSONファイル")
        return
    try:
        document = parse_server_export(await attachment.read())
    except ValueError as error:
        await message.channel.send(f"JSON設定を適用できませんでした: {error}")
        return

    try:
        rollback_json = export_server_to_json(message.guild)
        rollback_path = save_template_output(
            "get/result",
            f"server_rollback_before_import_{message.guild.id}",
            rollback_json,
            suffix=".json",
        )
        await send_template_output(
            message.channel,
            "JSON適用前のサーバー設定をロールバック用JSONとして送信します。"
            "このファイルを /server import に添付すると、適用前の設定へ戻せます。",
            rollback_path,
        )
    except (OSError, ValueError, discord.Forbidden, discord.HTTPException) as error:
        await message.channel.send(
            f"ロールバック用JSONを保存・送信できなかったため、設定は変更していません: {error}"
        )
        return

    try:
        counts = await apply_server_export(document, message.guild)
    except (ValueError, discord.Forbidden, discord.HTTPException) as error:
        await message.channel.send(f"JSON設定を適用できませんでした: {error}")
        return
    errors = counts.get("errors", [])
    details = " ".join(errors[:5])
    if len(errors) > 5:
        details += f" 他{len(errors) - 5}件"
    result_rows = counts.get("results", [])
    result_csv = build_import_result_csv(result_rows)
    result_path = save_template_output(
        "set/response",
        f"server_import_{message.guild.id}",
        result_csv,
    )
    successful = sum(row["result"] == "成功" for row in result_rows)
    partial = sum(row["result"] == "一部成功" for row in result_rows)
    failed = sum(row["result"] == "失敗" for row in result_rows)
    await send_template_output(
        message.channel,
        "JSON設定を適用しました。"
        f"ロール: {counts.get('roles_created', 0)}件作成、{counts.get('roles_updated', 0)}件更新、"
        f"{counts.get('roles_deleted', 0)}件削除、{counts.get('roles_skipped', 0)}件スキップ、"
        f"{counts.get('roles_failed', 0)}件失敗。"
        f"メンバー: {counts.get('members_updated', 0)}件更新、"
        f"{counts.get('members_skipped', 0)}件スキップ。"
        f"チャンネル: {counts.get('channels_created', 0)}件作成、"
        f"{counts.get('channels_updated', 0)}件更新、{counts.get('channels_deleted', 0)}件削除、"
        f"{counts.get('channels_skipped', 0)}件スキップ。"
        f"結果: 成功{successful}件、一部成功{partial}件、失敗{failed}件。結果CSVを添付します。"
        "JSONに含まれない管理可能なロール・チャンネルは削除し、メンバーのロール割り当てをJSONと一致させました。"
        "JSONに含まれないメンバーは、管理可能なロール割り当てを解除しました。"
        + (f" 一部の項目を適用できませんでした: {details}" if details else ""),
        result_path,
    )
