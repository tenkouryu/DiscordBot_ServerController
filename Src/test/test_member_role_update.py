import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from event.on_message.command.member.role_update import (
    update_member_roles_from_csv,
)


def make_role(role_id, name, *, default=False, managed=False):
    return SimpleNamespace(
        id=role_id,
        name=name,
        managed=managed,
        is_default=lambda: default,
    )


class MemberRoleUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_id_takes_priority_over_name_columns(self):
        selected_role = make_role(5, "Selected")
        by_id = SimpleNamespace(
            id=10,
            name="id_member",
            display_name="ID Member",
            roles=[],
            edit=AsyncMock(),
        )
        by_name = SimpleNamespace(
            id=11,
            name="name_member",
            display_name="Name Member",
            roles=[],
            edit=AsyncMock(),
        )
        guild = SimpleNamespace(
            members=[by_id, by_name],
            roles=[selected_role],
        )

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            "User ID,Name,Display Name,Role1\n"
            "10,name_member,Name Member,Selected\n",
        )
        rows = list(csv.reader(io.StringIO(result_csv)))

        self.assertEqual(success_count, 1)
        self.assertEqual(rows[1][-2:], ["成功", ""])
        by_id.edit.assert_awaited_once_with(
            roles=[selected_role],
            reason="CSVからメンバーロールを更新",
        )
        by_name.edit.assert_not_awaited()

    async def test_blank_user_id_falls_back_to_username_then_display_name(self):
        by_username_role = make_role(6, "Username Role")
        by_display_role = make_role(7, "Display Role")
        by_username = SimpleNamespace(
            id=10,
            name="username_match",
            display_name="Other Display",
            roles=[],
            edit=AsyncMock(),
        )
        by_display = SimpleNamespace(
            id=11,
            name="different_name",
            display_name="Display Match",
            roles=[],
            edit=AsyncMock(),
        )
        guild = SimpleNamespace(
            members=[by_username, by_display],
            roles=[by_username_role, by_display_role],
        )

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            "User ID,Name,Display Name,Role1\n"
            ",USERNAME_MATCH,Display Match,Username Role\n"
            ",not_found,display match,Display Role\n",
        )
        rows = list(csv.reader(io.StringIO(result_csv)))

        self.assertEqual(success_count, 2)
        by_username.edit.assert_awaited_once_with(
            roles=[by_username_role],
            reason="CSVからメンバーロールを更新",
        )
        by_display.edit.assert_awaited_once_with(
            roles=[by_display_role],
            reason="CSVからメンバーロールを更新",
        )
        self.assertEqual([row[-2] for row in rows[1:]], ["成功", "成功"])

    async def test_update_replaces_assignable_roles_and_preserves_managed_roles(self):
        everyone = make_role(1, "@everyone", default=True)
        old_role = make_role(2, "Old")
        managed_role = make_role(3, "Integration", managed=True)
        new_role = make_role(4, "New")
        member = SimpleNamespace(
            id=10,
            name="example_user",
            roles=[everyone, old_role, managed_role],
            edit=AsyncMock(),
        )
        guild = SimpleNamespace(
            members=[member],
            roles=[everyone, old_role, managed_role, new_role],
        )
        csv_text = (
            "Name,Display Name,Role1,Role2\n"
            "example_user,Example User,New,@everyone\n"
        )

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            csv_text,
        )
        rows = list(csv.reader(io.StringIO(result_csv)))

        self.assertEqual(success_count, 1)
        self.assertEqual(
            rows[0],
            ["Name", "Display Name", "Role1", "Role2", "result", "reason"],
        )
        self.assertEqual(
            rows[1],
            ["example_user", "Example User", "New", "@everyone", "成功", ""],
        )
        member.edit.assert_awaited_once_with(
            roles=[everyone, managed_role, new_role],
            reason="CSVからメンバーロールを更新",
        )

    async def test_unknown_role_is_reported_without_changing_member(self):
        member = SimpleNamespace(
            id=10,
            name="example_user",
            roles=[],
            edit=AsyncMock(),
        )
        guild = SimpleNamespace(
            members=[member],
            roles=[],
        )

        result_csv, success_count = await update_member_roles_from_csv(
            guild,
            "Name,Role1\nexample_user,Missing\n",
        )
        rows = list(csv.reader(io.StringIO(result_csv)))

        self.assertEqual(success_count, 0)
        self.assertEqual(rows[1][-2:], ["失敗", "ロール「Missing」が見つかりません。"])
        member.edit.assert_not_awaited()

    async def test_csv_requires_name_and_role_columns(self):
        guild = SimpleNamespace(members=[], roles=[])

        with self.assertRaisesRegex(ValueError, "User ID"):
            await update_member_roles_from_csv(guild, "Username\nexample_user\n")


if __name__ == "__main__":
    unittest.main()
