from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from event.on_message.command.server import export_json
from event.on_message.command.slash_commands import register_slash_commands
from function.file import template_output_service
from discord import app_commands


def fake_role(
    role_id: int,
    name: str,
    *,
    permissions: discord.Permissions | None = None,
    is_default: bool = False,
) -> MagicMock:
    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.name = name
    role.color = discord.Colour(0x123456)
    role.position = role_id
    role.managed = False
    role.hoist = False
    role.mentionable = False
    role.permissions = permissions or discord.Permissions.none()
    role.is_default.return_value = is_default
    return role


class ServerExportJsonTests(unittest.IsolatedAsyncioTestCase):
    def make_guild(self):
        everyone = fake_role(1, "@everyone", is_default=True)
        editor = fake_role(
            2,
            "Editor",
            permissions=discord.Permissions(manage_channels=True, view_channel=True),
        )
        member = MagicMock(spec=discord.Member)
        member.id = 20
        member.name = "user"
        member.display_name = "ユーザー"
        member.bot = False
        member.roles = [everyone, editor]

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 30
        channel.name = "general"
        channel.type = discord.ChannelType.text
        channel.position = 0
        channel.category_id = None
        channel.category = None
        channel.topic = "topic"
        channel.nsfw = False
        channel.slowmode_delay = 5
        channel.overwrites = {
            editor: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            member: discord.PermissionOverwrite(read_message_history=True),
        }

        guild = SimpleNamespace(
            id=10,
            name="テストサーバー",
            owner_id=20,
            roles=[editor, everyone],
            members=[member],
            channels=[channel],
        )
        return guild

    def test_export_json_contains_roles_member_role_ids_and_channel_overwrites(self):
        payload = export_json.export_server_to_json(self.make_guild())
        document = json.loads(payload.decode("utf-8"))

        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["guild"]["id"], "10")
        self.assertEqual([role["id"] for role in document["roles"]], ["1", "2"])
        self.assertTrue(document["roles"][1]["permissions"]["manage_channels"])
        self.assertEqual(document["members"][0]["role_ids"], ["1", "2"])
        self.assertEqual(document["members"][0]["display_name"], "ユーザー")
        channel = document["channels"][0]
        self.assertEqual(channel["type"], "text")
        self.assertEqual(channel["slowmode_seconds"], 5)
        overwrites = channel["permission_overwrites"]
        overwrite = next(item for item in overwrites if item["target_type"] == "role")
        self.assertEqual(overwrite["target_id"], "2")
        self.assertIn("view_channel", overwrite["allow"])
        self.assertIn("send_messages", overwrite["deny"])
        member_overwrite = next(item for item in overwrites if item["target_type"] == "member")
        self.assertEqual(member_overwrite["target_id"], "20")
        self.assertIn("read_message_history", member_overwrite["allow"])

    def test_export_rejects_missing_guild(self):
        with self.assertRaisesRegex(ValueError, "サーバー"):
            export_json.build_server_export(None)

    def test_output_service_accepts_json_but_rejects_other_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(template_output_service, "_TEMP_ROOT", new=Path(directory)):
                path = template_output_service.create_template_output_path(
                    "get/result", "server_export_10", suffix=".json"
                )
        self.assertEqual(path.suffix, ".json")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(template_output_service, "_TEMP_ROOT", new=Path(directory)):
                with self.assertRaises(ValueError):
                    template_output_service.create_template_output_path(
                        "get/result", "server_export_10", suffix=".xml"
                    )

    async def test_command_requires_both_manage_permissions(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            author=SimpleNamespace(
                guild_permissions=SimpleNamespace(
                    manage_roles=True,
                    manage_channels=False,
                    administrator=False,
                )
            ),
            channel=channel,
            guild=self.make_guild(),
        )

        await export_json.main(message)

        channel.send.assert_awaited_once_with(
            "サーバー情報のJSON取得には、ロール管理権限とチャンネル管理権限の両方が必要です。"
        )

    async def test_command_sends_json_attachment_for_users_with_both_permissions(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            author=SimpleNamespace(
                guild_permissions=SimpleNamespace(
                    manage_roles=True,
                    manage_channels=True,
                    administrator=False,
                )
            ),
            channel=channel,
            guild=self.make_guild(),
        )

        with (
            patch.object(export_json, "save_template_output", return_value=Path("snapshot.json")) as save,
            patch.object(export_json, "send_template_output", new_callable=AsyncMock) as send,
        ):
            await export_json.main(message)

        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs["suffix"], ".json")
        self.assertEqual(json.loads(save.call_args.args[2])["guild"]["name"], "テストサーバー")
        send.assert_awaited_once_with(
            channel,
            "サーバーロール、メンバーロール、チャンネル情報をJSONで送信します。",
            Path("snapshot.json"),
        )

    async def test_slash_command_routes_to_json_export_handler(self):
        client = discord.Client(intents=discord.Intents.none())
        tree = app_commands.CommandTree(client)
        register_slash_commands(tree)
        command = tree.get_command("server").get_command("export")
        interaction = SimpleNamespace(
            client=client,
            user=object(),
            channel=None,
            response=SimpleNamespace(defer=AsyncMock()),
        )

        with patch.object(export_json, "main", new_callable=AsyncMock) as handler:
            await command.callback(interaction)

        handler.assert_awaited_once()
        self.assertEqual(handler.await_args.args[0].content, "/server_export")


if __name__ == "__main__":
    unittest.main()
