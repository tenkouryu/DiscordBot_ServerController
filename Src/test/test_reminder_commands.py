import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from discord import app_commands

from event.on_message.command import slash_commands


class ReminderCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        client = discord.Client(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(client)
        slash_commands.register_slash_commands(self.tree)
        self.group = self.tree.get_command("reminder")
        self.add_command = self.group.get_command("add")
        self.remove_command = self.group.get_command("remove")
        self.import_command = self.group.get_command("import")
        self.template_command = self.group.get_command("template")

    def _interaction(self, *, manage_guild=True):
        interaction = SimpleNamespace()
        interaction.permissions = SimpleNamespace(
            manage_guild=manage_guild,
            administrator=False,
        )
        interaction.response = SimpleNamespace(send_message=AsyncMock())
        return interaction

    async def test_add_command_registers_reminder_and_returns_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            config.mkdir()
            (config / "reminders.json").write_text(
                '{"reminders": []}\n',
                encoding="utf-8",
            )
            interaction = self._interaction()
            channel = SimpleNamespace(id=123456)
            user = SimpleNamespace(id=234567)
            role = SimpleNamespace(id=345678)

            with patch.object(slash_commands, "application_root", return_value=root):
                await self.add_command.callback(
                    interaction,
                    datetime_text="2026-10-25 10:00",
                    channel=channel,
                    content="test reminder",
                    mention_user=user,
                    mention_role=role,
                )

            interaction.response.send_message.assert_awaited_once()
            response = interaction.response.send_message.await_args.args[0]
            self.assertIn("リマインダーを登録しました", response)
            self.assertIn("ID:", response)
            self.assertTrue(
                interaction.response.send_message.await_args.kwargs["ephemeral"]
            )

    async def test_add_command_requires_manage_guild(self):
        interaction = self._interaction(manage_guild=False)

        with patch.object(slash_commands, "add_reminder") as add_mock:
            await self.add_command.callback(
                interaction,
                datetime_text="2026-10-25 10:00",
                channel=SimpleNamespace(id=123456),
                content="test reminder",
            )

        add_mock.assert_not_called()
        self.assertIn(
            "権限が必要",
            interaction.response.send_message.await_args.args[0],
        )

    async def test_remove_command_deletes_reminder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            config.mkdir()
            (config / "reminders.json").write_text(
                '{"reminders": [{"id":"reminder-id","datetime":"2026-10-25T10:00:00+09:00","channel_id":"123456","content":"reminder"}]}\n',
                encoding="utf-8",
            )
            interaction = self._interaction()

            with patch.object(slash_commands, "application_root", return_value=root):
                await self.remove_command.callback(
                    interaction,
                    reminder_id="reminder-id",
                )

            interaction.response.send_message.assert_awaited_once()
            self.assertIn(
                "削除しました",
                interaction.response.send_message.await_args.args[0],
            )
            self.assertEqual(
                (config / "reminders.json").read_text(encoding="utf-8").strip(),
                '{\n  "reminders": []\n}',
            )

    async def test_import_command_registers_csv_for_guild_channels(self):
        interaction = self._interaction()
        interaction.guild = SimpleNamespace(
            text_channels=[SimpleNamespace(id=123456)]
        )
        interaction.response.defer = AsyncMock()
        interaction.followup = SimpleNamespace(send=AsyncMock())
        attachment = SimpleNamespace(
            filename="reminders.csv",
            size=100,
            read=AsyncMock(
                return_value=(
                    "datetime,channel_id,content\n"
                    "2026-10-25 10:00,123456,Reminder\n"
                ).encode("utf-8"),
            ),
        )

        with patch.object(
            slash_commands,
            "register_reminders_csv_for_guild",
            new_callable=AsyncMock,
            return_value=[{"id": "registered"}],
        ) as register_mock:
            await self.import_command.callback(interaction, file=attachment)

        register_mock.assert_awaited_once()
        self.assertEqual(register_mock.await_args.args[2], interaction.guild)
        interaction.response.defer.assert_awaited_once_with(
            ephemeral=True,
            thinking=True,
        )
        interaction.followup.send.assert_awaited_once()
        self.assertIn(
            "1件",
            interaction.followup.send.await_args.args[0],
        )

    async def test_template_command_sends_csv_attachment(self):
        interaction = self._interaction()

        await self.template_command.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        file = interaction.response.send_message.await_args.kwargs["file"]
        self.assertEqual(file.filename, "reminder_template.csv")


if __name__ == "__main__":
    unittest.main()
