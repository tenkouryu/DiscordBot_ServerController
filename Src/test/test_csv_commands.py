import csv
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from event.on_message.command.channel import set as channel_set
from event.on_message.command.member import role_set as member_role_set
from event.on_message.command.member import role_update as member_role_update
from event.on_message.command.scenario import set as scenario_set
from event.on_message.command.server import role_set as server_role_set
from function.scenario.scenario_service import register_scenario_csv

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "release" / "tools" / "templates" / "set" / "input"


def make_attachment(text, filename="input.csv", raw=None):
    data = raw if raw is not None else text.encode("utf-8-sig")
    return SimpleNamespace(filename=filename, read=AsyncMock(return_value=data))


def make_message(attachments, *, content="/cmd", allowed=True, guild=None):
    perms = SimpleNamespace(manage_roles=allowed, manage_channels=allowed, administrator=False)
    return SimpleNamespace(
        content=content,
        attachments=attachments,
        author=SimpleNamespace(guild_permissions=perms),
        channel=SimpleNamespace(send=AsyncMock()),
        guild=guild or SimpleNamespace(id=1, members=[], roles=[], channels=[], categories=[]),
    )


def parse(result_bytes):
    return list(csv.reader(io.StringIO(result_bytes.decode("utf-8-sig"))))


class CsvCommandFixture:
    """各CSVコマンドの main を、保存/送信だけ差し替えて実行する。"""

    module = None

    def run_main(self, message, **extra):
        saved = {}

        def fake_save(folder, name, data):
            saved["data"] = data
            return "result.csv"

        send = AsyncMock()
        patches = [
            patch.object(self.module, "save_template_output", fake_save),
            patch.object(self.module, "send_template_output", send),
        ]
        return saved, send, patches

    async def call(self, message):
        saved, send, patches = self.run_main(message)
        for p in patches:
            p.start()
        try:
            await self.module.main(message)
        finally:
            for p in patches:
                p.stop()
        return saved, send


class CommonCsvCommandTests:
    """全CSVコマンド共通の入口チェック。"""

    async def test_help_option_does_not_need_attachment(self):
        message = make_message([], content="/cmd -h")
        saved, send = await self.call(message)
        message.channel.send.assert_awaited_once()
        self.assertEqual(saved, {})

    async def test_missing_attachment_is_reported(self):
        message = make_message([])
        saved, send = await self.call(message)
        message.channel.send.assert_awaited_once()
        self.assertEqual(saved, {})

    async def test_non_csv_attachment_is_ignored(self):
        message = make_message([make_attachment("x", filename="a.txt")])
        saved, send = await self.call(message)
        message.channel.send.assert_awaited_once()
        self.assertEqual(saved, {})

    async def test_invalid_encoding_is_reported_without_crash(self):
        message = make_message([make_attachment("", raw=b"\xff\xfe\x00bad\x80")])
        saved, send = await self.call(message)
        message.channel.send.assert_awaited_once()
        self.assertEqual(saved, {})

    async def test_empty_csv_does_not_crash(self):
        message = make_message([make_attachment("")])
        saved, send = await self.call(message)
        self.assertEqual(saved, {})
        self.assertTrue(message.channel.send.await_count == 1 or send.await_count == 1)


class PermissionMixin:
    async def test_denied_without_permission(self):
        message = make_message([make_attachment("name\nx")], allowed=False)
        saved, send = await self.call(message)
        message.channel.send.assert_awaited_once()
        self.assertEqual(saved, {})


class ServerRoleSetTests(CsvCommandFixture, CommonCsvCommandTests, PermissionMixin, unittest.IsolatedAsyncioTestCase):
    module = server_role_set

    async def test_missing_name_column_is_reported(self):
        message = make_message([make_attachment("color\n#fff")])
        saved, _ = await self.call(message)
        self.assertIn("name", message.channel.send.await_args.args[0])
        self.assertEqual(saved, {})

    async def test_rows_are_applied_and_result_columns_added(self):
        edit = AsyncMock()
        csv_text = "name,color,manage_messages\nA,#ff0000,true\nB,,maybe\n,,true\n"
        message = make_message([make_attachment(csv_text)])
        with patch.object(server_role_set.edit_roll, "edit_role_settings", edit):
            saved, send = await self.call(message)

        edit.assert_awaited_once_with(message.guild, "A", "#ff0000", {"manage_messages": True})
        rows = parse(saved["data"])
        self.assertEqual(rows[0], ["name", "color", "manage_messages", "result", "reason"])
        self.assertEqual([r[3] for r in rows[1:]], ["成功", "失敗", "失敗"])
        self.assertIn("true または false", rows[2][4])
        self.assertIn("ロール名が空", rows[3][4])
        self.assertIn("1件", send.await_args.args[1])

    async def test_shipped_template_does_not_crash(self):
        text = (TEMPLATE_DIR / "server_role_template.csv").read_bytes()
        message = make_message([make_attachment("", raw=text)])
        edit = AsyncMock()
        with patch.object(server_role_set.edit_roll, "edit_role_settings", edit):
            saved, _ = await self.call(message)
        self.assertEqual(parse(saved["data"])[0][-2:], ["result", "reason"])


class MemberRoleSetTests(CsvCommandFixture, CommonCsvCommandTests, PermissionMixin, unittest.IsolatedAsyncioTestCase):
    module = member_role_set

    def _guild(self):
        role = SimpleNamespace(id=10, name="RoleA", managed=False, is_default=lambda: False)
        member = SimpleNamespace(
            id=5, name="alice", display_name="Alice",
            add_roles=AsyncMock(), remove_roles=AsyncMock(),
        )
        guild = SimpleNamespace(id=1, members=[member], roles=[role], channels=[], categories=[])
        return guild, member, role

    async def test_missing_required_column_is_reported(self):
        message = make_message([make_attachment("ユーザー名,ロール1\nalice,RoleA")])
        saved, _ = await self.call(message)
        self.assertIn("追加/削除", message.channel.send.await_args.args[0])
        self.assertEqual(saved, {})

    async def test_add_remove_and_invalid_rows(self):
        guild, member, role = self._guild()
        csv_text = (
            "追加/削除,ユーザーID,ユーザー名,表示名,ロール1,ロール2\n"
            "追加,5,,,RoleA,\n"
            "削除,,alice,,RoleA,\n"
            "変更,,alice,,RoleA,\n"
            "追加,,nobody,,RoleA,\n"
        )
        message = make_message([make_attachment(csv_text)], guild=guild)
        saved, send = await self.call(message)

        member.add_roles.assert_awaited_once_with(role)
        member.remove_roles.assert_awaited_once_with(role)
        rows = parse(saved["data"])
        self.assertEqual([r[-2] for r in rows[1:]], ["成功", "成功", "失敗", "失敗"])

    async def test_shipped_template_does_not_crash(self):
        text = (TEMPLATE_DIR / "member_role_template.csv").read_bytes()
        guild, _, _ = self._guild()
        message = make_message([make_attachment("", raw=text)], guild=guild)
        saved, _ = await self.call(message)
        self.assertEqual(parse(saved["data"])[0][-2:], ["result", "reason"])


class MemberRoleUpdateTests(CsvCommandFixture, CommonCsvCommandTests, PermissionMixin, unittest.IsolatedAsyncioTestCase):
    module = member_role_update

    async def test_missing_role_columns_is_reported(self):
        message = make_message([make_attachment("User ID,Name\n1,a")])
        saved, _ = await self.call(message)
        self.assertIn("ロール列", message.channel.send.await_args.args[0])
        self.assertEqual(saved, {})

    async def test_roles_are_replaced_and_results_reported(self):
        member = SimpleNamespace(id=5, name="alice", display_name="Alice")
        guild = SimpleNamespace(id=1, members=[member], roles=[], channels=[], categories=[])
        csv_text = "User ID,Name,Display Name,Role1\n5,alice,Alice,RoleA\n,ghost,,RoleA\n"
        replace = AsyncMock(return_value=None)
        message = make_message([make_attachment(csv_text)], guild=guild)
        with patch.object(member_role_update, "_replace_member_roles", replace):
            saved, send = await self.call(message)

        replace.assert_awaited_once()
        rows = parse(saved["data"])
        self.assertEqual([r[-2] for r in rows[1:]], ["成功", "失敗"])
        self.assertIn("1件", send.await_args.args[1])


class ChannelSetTests(CsvCommandFixture, CommonCsvCommandTests, PermissionMixin, unittest.IsolatedAsyncioTestCase):
    module = channel_set

    async def test_missing_columns_is_reported(self):
        message = make_message([make_attachment("name,type\na,text")])
        saved, _ = await self.call(message)
        self.assertIn("category", message.channel.send.await_args.args[0])
        self.assertEqual(saved, {})

    async def test_channels_are_created_and_invalid_rows_fail(self):
        csv_text = (
            "name,type,category,role_1,user_1\n"
            "general,text,Cat,RoleA,\n"
            "voice1,voice,,,\n"
            "bad,forum,,,\n"
            ",text,,,\n"
        )
        created = SimpleNamespace(name="x")
        text_create = AsyncMock(return_value=created)
        voice_create = AsyncMock(return_value=created)
        sync = AsyncMock()
        message = make_message([make_attachment(csv_text)])
        with patch.object(channel_set.edit_channel, "create_text_channel", text_create), \
             patch.object(channel_set.edit_channel, "create_voice_channel", voice_create), \
             patch.object(channel_set.edit_channel, "sync_channel_role_access", sync):
            saved, send = await self.call(message)

        text_create.assert_awaited_once_with(message.guild, "general", "Cat")
        voice_create.assert_awaited_once_with(message.guild, "voice1", None)
        sync.assert_awaited_once_with(created, ["RoleA"])
        rows = parse(saved["data"])
        self.assertEqual([r[-2] for r in rows[1:]], ["成功", "成功", "失敗", "失敗"])

    async def test_shipped_template_does_not_crash(self):
        text = (TEMPLATE_DIR / "channel_template.csv").read_bytes()
        message = make_message([make_attachment("", raw=text)])
        saved, _ = await self.call(message)
        self.assertEqual(parse(saved["data"])[0][-2:], ["result", "reason"])


class ScenarioSetTests(CsvCommandFixture, CommonCsvCommandTests, unittest.IsolatedAsyncioTestCase):
    module = scenario_set

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.definitions = Path(self._tmp.name) / "definitions.json"
        patcher = patch.object(
            scenario_set,
            "register_scenario_csv",
            lambda text: register_scenario_csv(text, self.definitions),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_missing_columns_marks_rows_failed(self):
        message = make_message([make_attachment("scenario_id,step\ns,1\n")])
        saved, send = await self.call(message)
        rows = parse(saved["data"])
        self.assertEqual(rows[1][-2], "失敗")
        self.assertIn("0ステップ", send.await_args.args[1])

    async def test_invalid_step_marks_rows_failed(self):
        header = "scenario_id,step,instruction,completion_type,completion_value,response\n"
        message = make_message([make_attachment(header + "s,abc,i,keyword,k,r\n")])
        saved, _ = await self.call(message)
        self.assertEqual(parse(saved["data"])[1][-2], "失敗")
        self.assertFalse(self.definitions.exists())

    async def test_valid_csv_is_registered(self):
        header = "scenario_id,step,instruction,completion_type,completion_value,response\n"
        message = make_message([make_attachment(header + "s,1,i1,keyword,k,r1\ns,2,i2,keyword,k,r2\n")])
        saved, send = await self.call(message)
        self.assertEqual([r[-2] for r in parse(saved["data"])[1:]], ["成功", "成功"])
        self.assertIn("2ステップ", send.await_args.args[1])
        self.assertTrue(self.definitions.exists())

    async def test_shipped_templates_register(self):
        for name in ("scenario_template.csv", "team_match_scenario.csv"):
            with self.subTest(template=name):
                text = (TEMPLATE_DIR / name).read_bytes()
                message = make_message([make_attachment("", raw=text)])
                saved, _ = await self.call(message)
                results = {r[-2] for r in parse(saved["data"])[1:]}
                self.assertEqual(results, {"成功"})


if __name__ == "__main__":
    unittest.main()
