import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from event.on_message.command.member.role_set import (
    _find_member,
    update_member_roles_from_csv,
)
from event.on_message.command.member.role_template import main as role_template_main
from event.on_message.command.server.member_list import _build_member_list_csv


def make_role(role_id, name):
    return SimpleNamespace(
        id=role_id,
        name=name,
        managed=False,
        is_default=lambda: False,
    )


class MemberRoleSetCsvTests(unittest.IsolatedAsyncioTestCase):
    async def test_role_template_includes_id_and_multiple_role_columns(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            content="/member_role_template",
            channel=channel,
        )

        await role_template_main(message)

        attachment = channel.send.await_args.kwargs["file"]
        attachment.fp.seek(0)
        rows = list(
            csv.reader(
                io.StringIO(attachment.fp.read().decode("utf-8-sig"))
            )
        )
        self.assertEqual(
            rows[0],
            ["追加/削除", "ユーザーID", "ユーザー名", "表示名", "ロール1", "ロール2"],
        )

    async def test_server_member_list_includes_user_id(self):
        member = SimpleNamespace(
            id=123,
            name="example_user",
            display_name="Example User",
            roles=[make_role(1, "Role A"), make_role(2, "Role B")],
        )

        rows = list(
            csv.reader(
                io.StringIO(
                    _build_member_list_csv([member]).decode("utf-8-sig")
                )
            )
        )

        self.assertEqual(
            rows,
            [
                ["User ID", "Name", "Display Name", "Role1", "Role2"],
                ["123", "example_user", "Example User", "Role A", "Role B"],
            ],
        )

    async def test_user_id_takes_priority_and_multiple_roles_are_added(self):
        roles = [make_role(1, "Role A"), make_role(2, "Role B")]
        id_match = SimpleNamespace(
            id=123,
            name="id_match",
            display_name="ID Match",
            add_roles=AsyncMock(),
            remove_roles=AsyncMock(),
        )
        username_match = SimpleNamespace(
            id=456,
            name="username_match",
            display_name="Username Match",
            add_roles=AsyncMock(),
            remove_roles=AsyncMock(),
        )
        guild = SimpleNamespace(members=[id_match, username_match], roles=roles)

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            "追加/削除,ユーザーID,ユーザー名,表示名,ロール1,ロール2\n"
            "追加,123,username_match,Username Match,Role A,Role B\n",
        )
        rows = list(csv.reader(io.StringIO(result_csv)))

        self.assertEqual(success_count, 1)
        self.assertEqual(rows[1][-2:], ["成功", ""])
        id_match.add_roles.assert_has_awaits(
            [call(roles[0]), call(roles[1])]
        )
        username_match.add_roles.assert_not_awaited()

    async def test_username_then_display_name_are_fallbacks(self):
        by_username = SimpleNamespace(
            id=123,
            name="example_user",
            display_name="User Display",
        )
        by_display_name = SimpleNamespace(
            id=456,
            name="different_user",
            display_name="Target Display",
        )
        guild = SimpleNamespace(members=[by_username, by_display_name])

        self.assertEqual(
            _find_member(guild, "", "EXAMPLE_USER", "Target Display")[0],
            by_username,
        )
        self.assertEqual(
            _find_member(guild, "", "missing_user", "target display")[0],
            by_display_name,
        )

    async def test_unknown_user_id_does_not_fall_back_to_name(self):
        member = SimpleNamespace(
            id=123,
            name="example_user",
            display_name="Example User",
        )
        guild = SimpleNamespace(members=[member])

        found, error = _find_member(
            guild,
            "999",
            "example_user",
            "Example User",
        )

        self.assertIsNone(found)
        self.assertIn("ユーザーID", error)

    async def test_old_single_role_column_remains_supported(self):
        role = make_role(1, "Role A")
        member = SimpleNamespace(
            id=123,
            name="example_user",
            display_name="Example User",
            add_roles=AsyncMock(),
            remove_roles=AsyncMock(),
        )
        guild = SimpleNamespace(members=[member], roles=[role])

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            "追加/削除,ユーザー名,ロール\n追加,example_user,Role A\n",
        )

        self.assertEqual(success_count, 1)
        member.add_roles.assert_awaited_once_with(role)
        self.assertIn("成功", result_csv)


if __name__ == "__main__":
    unittest.main()
