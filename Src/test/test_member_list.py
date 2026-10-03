import csv
import io
import unittest
from types import SimpleNamespace

from event.on_message.command.server.member_list import _build_member_list_csv


class MemberListTests(unittest.TestCase):
    def test_build_csv_outputs_each_role_in_its_own_column(self):
        members = [
            SimpleNamespace(
                name="user_one",
                display_name="User One",
                roles=[SimpleNamespace(name="role1"), SimpleNamespace(name="role2")],
            ),
            SimpleNamespace(
                name="user_two",
                display_name="User Two",
                roles=[SimpleNamespace(name="role3")],
            ),
        ]

        csv_data = _build_member_list_csv(members)
        rows = list(csv.reader(io.StringIO(csv_data.decode("utf-8-sig"))))

        self.assertEqual(rows[0], ["Name", "Display Name", "Role1", "Role2"])
        self.assertEqual(rows[1], ["user_one", "User One", "role1", "role2"])
        self.assertEqual(rows[2], ["user_two", "User Two", "role3", ""])

    def test_build_csv_without_roles_has_only_member_columns(self):
        member = SimpleNamespace(name="user", display_name="User", roles=[])

        rows = list(
            csv.reader(
                io.StringIO(_build_member_list_csv([member]).decode("utf-8-sig"))
            )
        )

        self.assertEqual(rows, [["Name", "Display Name"], ["user", "User"]])


if __name__ == "__main__":
    unittest.main()
