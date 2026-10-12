from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from event.on_message.command.server import export_json
from event.on_message.command.server import import_json
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

    async def test_import_synchronizes_roles_and_member_assignments(self):
        target_everyone = fake_role(101, "@everyone", is_default=True)
        target_editor = fake_role(102, "Editor")
        target_extra = fake_role(103, "Target-only")
        target_channel = MagicMock(spec=discord.VoiceChannel)
        target_channel.id = 301
        target_channel.name = "unused"
        target_channel.type = discord.ChannelType.voice
        target_channel.delete = AsyncMock()
        target_member = MagicMock(spec=discord.Member)
        target_member.id = 220
        target_member.name = "user"
        target_member.display_name = "移行先ユーザー"
        target_member.roles = [target_everyone, target_editor, target_extra]
        target_member.add_roles = AsyncMock()
        target_member.remove_roles = AsyncMock()
        unlisted_member = MagicMock(spec=discord.Member)
        unlisted_member.id = 221
        unlisted_member.name = "unlisted-user"
        unlisted_member.display_name = "移行先のみのユーザー"
        unlisted_member.roles = [target_everyone, target_editor, target_extra]
        unlisted_member.remove_roles = AsyncMock()

        guild = SimpleNamespace(
            default_role=target_everyone,
            roles=[target_everyone, target_editor, target_extra],
            members=[target_member, unlisted_member],
            channels=[target_channel],
            create_role=AsyncMock(),
            edit_role_positions=AsyncMock(),
        )
        document = {
            "schema_version": 1,
            "guild": {"id": "10", "name": "移行元"},
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "color": "#000000",
                    "permissions": {"view_channel": True},
                },
                {
                    "id": "2",
                    "name": "Editor",
                    "is_default": False,
                    "managed": False,
                    "color": "#123456",
                    "position": 2,
                    "hoist": True,
                    "mentionable": False,
                    "permissions": {"manage_channels": True},
                },
            ],
            "members": [
                {
                    "id": "20",
                    "name": "user",
                    "display_name": "移行元ユーザー",
                    "role_ids": ["1"],
                }
            ],
            "channels": [],
        }

        counts = await import_json.apply_server_export(document, guild)

        target_editor.edit.assert_awaited_once()
        target_everyone.edit.assert_awaited_once()
        target_member.add_roles.assert_not_awaited()
        self.assertCountEqual(
            target_member.remove_roles.await_args.args,
            [target_editor, target_extra],
        )
        self.assertCountEqual(
            unlisted_member.remove_roles.await_args.args,
            [target_editor, target_extra],
        )
        target_extra.delete.assert_awaited_once()
        target_channel.delete.assert_awaited_once()
        guild.create_role.assert_not_awaited()
        guild.edit_role_positions.assert_awaited_once()
        self.assertEqual(counts["members_updated"], 2)
        self.assertEqual(counts["roles_updated"], 2)
        self.assertEqual(counts["roles_deleted"], 1)
        self.assertEqual(counts["channels_deleted"], 1)
        self.assertEqual(
            [row["result"] for row in counts["results"][:4]],
            ["成功", "成功", "成功", "成功"],
        )
        result_by_target = {
            (row["対象種別"], row["名前"], row["処理"]): row["result"]
            for row in counts["results"]
        }
        self.assertEqual(result_by_target[("ロール", "Target-only", "削除")], "成功")
        self.assertEqual(result_by_target[("チャンネル", "unused", "削除")], "成功")
        self.assertEqual(
            result_by_target[("メンバー", "unlisted-user", "JSON対象外ロール削除")],
            "成功",
        )

    def test_import_result_csv_includes_result_and_reason_columns(self):
        payload = import_json.build_import_result_csv(
            [
                import_json._result_row("ロール", "Editor", "更新", "成功"),
                import_json._result_row("チャンネル", "general", "更新", "失敗", "権限不足"),
            ]
        )

        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        self.assertEqual(list(rows[0]), ["対象種別", "名前", "処理", "result", "reason"])
        self.assertEqual(rows[0]["result"], "成功")
        self.assertEqual(rows[1]["result"], "失敗")
        self.assertEqual(rows[1]["reason"], "権限不足")

    def test_import_rejects_invalid_permission_names_and_overlapping_overwrites(self):
        invalid = {
            "schema_version": 1,
            "guild": {},
            "roles": [
                {
                    "id": "1",
                    "name": "bad",
                    "permissions": {"not_a_permission": True},
                }
            ],
            "members": [],
            "channels": [],
        }
        with self.assertRaisesRegex(ValueError, "未対応の権限"):
            import_json.parse_server_export(json.dumps(invalid).encode())

        invalid["roles"] = [
            {
                "id": "everyone",
                "name": "@everyone",
                "is_default": True,
                "color": "#000000",
                "permissions": {},
            }
        ]
        invalid["channels"] = [
            {
                "id": "2",
                "name": "general",
                "type": "text",
                "position": 0,
                "permission_overwrites": [
                    {
                        "target_type": "role",
                        "target_id": "1",
                        "target_name": "role",
                        "allow": ["view_channel"],
                        "deny": ["view_channel"],
                    }
                ],
            }
        ]
        invalid["roles"] = [
            {
                "id": "everyone",
                "name": "@everyone",
                "is_default": True,
                "color": "#000000",
                "permissions": {},
            },
            {
                "id": "1",
                "name": "role",
                "is_default": False,
                "color": "#000000",
                "permissions": {},
            }
        ]
        with self.assertRaisesRegex(ValueError, "競合"):
            import_json.parse_server_export(json.dumps(invalid).encode())

    async def test_channel_import_replaces_unlisted_overwrites(self):
        target_role = fake_role(102, "Editor")
        target_extra_role = fake_role(103, "Target-only")
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 300
        channel.name = "general"
        channel.type = discord.ChannelType.text
        channel.overwrites = {
            target_extra_role: discord.PermissionOverwrite(view_channel=True)
        }
        channel.edit = AsyncMock(return_value=None)
        guild = SimpleNamespace(
            roles=[target_role, target_extra_role],
            channels=[channel],
            create_category=AsyncMock(),
            create_text_channel=AsyncMock(),
        )
        source = {
            "id": "30",
            "name": "general",
            "type": "text",
            "position": 0,
            "category_name": None,
            "permission_overwrites": [
                {
                    "target_type": "role",
                    "target_id": "2",
                    "target_name": "Editor",
                    "allow": ["send_messages"],
                    "deny": [],
                }
            ],
            "topic": None,
            "nsfw": False,
            "slowmode_seconds": 0,
        }

        result, created, warnings = await import_json._apply_channel(
            guild,
            source,
            {},
            {"2": {"id": "2", "name": "Editor"}},
            {},
        )

        self.assertIs(result, channel)
        self.assertFalse(created)
        self.assertEqual(warnings, [])
        channel.edit.assert_awaited_once()
        overwrites = channel.edit.await_args.kwargs["overwrites"]
        self.assertIn(target_role, overwrites)
        self.assertNotIn(target_extra_role, overwrites)
        self.assertTrue(overwrites[target_role].send_messages)

    async def test_import_requires_both_manage_permissions_and_json_attachment(self):
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
            attachments=[],
        )

        await import_json.main(message)

        channel.send.assert_awaited_once_with(
            "サーバー設定のJSON適用には、ロール管理権限とチャンネル管理権限の両方が必要です。"
        )

    async def test_import_sends_rollback_json_before_applying_and_reports_sync_policy(self):
        channel = SimpleNamespace(send=AsyncMock())
        document = {
            "schema_version": 1,
            "guild": {"id": "10", "name": "source"},
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "color": "#000000",
                    "permissions": {},
                }
            ],
            "members": [],
            "channels": [],
        }
        attachment = SimpleNamespace(
            filename="server_export.json",
            read=AsyncMock(return_value=json.dumps(document).encode()),
        )
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
            attachments=[attachment],
        )

        events = []

        async def send_output(channel_arg, message_text, path):
            events.append(("send", message_text, path))

        async def apply_export(document_arg, guild_arg):
            events.append(("apply", document_arg, guild_arg))
            return {"errors": [], "results": []}

        with (
            patch.object(
                import_json,
                "apply_server_export",
                new=AsyncMock(side_effect=apply_export),
            ) as apply,
            patch.object(
                import_json,
                "export_server_to_json",
                return_value=b'{"rollback": true}',
            ) as export_snapshot,
            patch.object(
                import_json,
                "save_template_output",
                side_effect=[Path("rollback.json"), Path("result.csv")],
            ) as save_output,
            patch.object(
                import_json,
                "send_template_output",
                new=AsyncMock(side_effect=send_output),
            ) as send_output_mock,
        ):
            await import_json.main(message)

        apply.assert_awaited_once()
        export_snapshot.assert_called_once_with(message.guild)
        self.assertEqual(apply.await_args.args[0], document)
        self.assertEqual(events[0][0], "send")
        self.assertIn("ロールバック用JSON", events[0][1])
        self.assertEqual(events[1][0], "apply")
        self.assertEqual(save_output.call_count, 2)
        self.assertEqual(
            save_output.call_args_list[0].args[:2],
            ("get/result", "server_rollback_before_import_10"),
        )
        self.assertEqual(save_output.call_args_list[0].args[2], b'{"rollback": true}')
        self.assertEqual(save_output.call_args_list[0].kwargs["suffix"], ".json")
        self.assertEqual(
            save_output.call_args_list[1].args[:2],
            ("set/response", "server_import_10"),
        )
        self.assertTrue(save_output.call_args_list[1].args[2].startswith(b"\xef\xbb\xbf"))
        self.assertEqual(send_output_mock.await_count, 2)
        self.assertIn(
            "JSONに含まれない管理可能なロール・チャンネルは削除",
            send_output_mock.await_args.args[1],
        )
        self.assertIn(
            "メンバーのロール割り当てをJSONと一致",
            send_output_mock.await_args.args[1],
        )
        self.assertIn("結果CSVを添付します。", send_output_mock.await_args.args[1])

    async def test_import_does_not_apply_when_rollback_json_cannot_be_sent(self):
        channel = SimpleNamespace(send=AsyncMock())
        document = {
            "schema_version": 1,
            "guild": {"id": "10", "name": "source"},
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "color": "#000000",
                    "permissions": {},
                }
            ],
            "members": [],
            "channels": [],
        }
        attachment = SimpleNamespace(
            filename="server_export.json",
            read=AsyncMock(return_value=json.dumps(document).encode()),
        )
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
            attachments=[attachment],
        )
        send_error = discord.HTTPException(
            response=SimpleNamespace(status=500, reason="upload failed"),
            message="upload failed",
        )

        with (
            patch.object(
                import_json,
                "apply_server_export",
                new=AsyncMock(),
            ) as apply,
            patch.object(
                import_json,
                "export_server_to_json",
                return_value=b"{}",
            ),
            patch.object(
                import_json,
                "save_template_output",
                return_value=Path("rollback.json"),
            ),
            patch.object(
                import_json,
                "send_template_output",
                new=AsyncMock(side_effect=send_error),
            ),
        ):
            await import_json.main(message)

        apply.assert_not_awaited()
        channel.send.assert_awaited_once()
        self.assertIn("設定は変更していません", channel.send.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
