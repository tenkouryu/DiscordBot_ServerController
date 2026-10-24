import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from function.reminder.reminder_service import (
    add_reminder,
    create_reminder_csv_template,
    delete_reminder,
    parse_reminder_csv,
    process_due_reminders,
    register_reminders_csv,
    register_reminders_csv_for_guild,
)


class ReminderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_csv_names_resolve_case_insensitively_to_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            reminders_path.write_text('{"reminders": []}\n', encoding="utf-8")
            member = SimpleNamespace(id=234567, name="user_name", display_name="User Display")
            second_member = SimpleNamespace(
                id=456789,
                name="Second_User",
                display_name="Second User",
            )
            role = SimpleNamespace(id=345678, name="Raid Team")
            guild = SimpleNamespace(
                roles=[role],
                text_channels=[SimpleNamespace(id=123456)],
            )

            async def fetch_members(limit=None):
                self.assertIsNone(limit)
                yield member
                yield second_member

            guild.fetch_members = fetch_members
            csv_text = (
                "datetime,channel_id,content,mention_users,mention_roles\n"
                "2026-10-25 10:00,123456,Reminder,user display;second_user,raid team\n"
            )

            added = await register_reminders_csv_for_guild(
                reminders_path,
                csv_text,
                guild,
                now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(added[0]["mention_users"], ["234567", "456789"])
            self.assertEqual(added[0]["mention_roles"], ["345678"])
            stored = json.loads(reminders_path.read_text(encoding="utf-8"))["reminders"]
            self.assertEqual(stored[0]["mention_users"], ["234567", "456789"])
            self.assertEqual(stored[0]["mention_roles"], ["345678"])

    async def test_csv_name_resolution_rejects_ambiguous_user_names(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            original = '{"reminders": []}\n'
            reminders_path.write_text(original, encoding="utf-8")
            guild = SimpleNamespace(
                roles=[],
                text_channels=[SimpleNamespace(id=123456)],
            )

            async def fetch_members(limit=None):
                yield SimpleNamespace(id=234567, name="same", display_name="Same")
                yield SimpleNamespace(id=345678, name="other", display_name="Same")

            guild.fetch_members = fetch_members
            csv_text = (
                "datetime,channel_id,content,mention_users\n"
                "2026-10-25 10:00,123456,Reminder,Same\n"
            )

            with self.assertRaisesRegex(ValueError, "複数一致"):
                await register_reminders_csv_for_guild(
                    reminders_path,
                    csv_text,
                    guild,
                    now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
                )

            self.assertEqual(reminders_path.read_text(encoding="utf-8"), original)

    def test_add_and_delete_reminder(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            reminders_path.write_text('{"reminders": []}\n', encoding="utf-8")

            reminder = add_reminder(
                reminders_path,
                "2026-10-25 10:00",
                123456,
                "test reminder",
                mention_users=[234567],
                mention_roles=[345678],
                now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
            )

            stored = json.loads(reminders_path.read_text(encoding="utf-8"))["reminders"]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["id"], reminder["id"])
            self.assertEqual(stored[0]["datetime"], "2026-10-25T10:00:00+09:00")
            self.assertEqual(stored[0]["mention_users"], ["234567"])
            self.assertEqual(stored[0]["mention_roles"], ["345678"])

            removed = delete_reminder(reminders_path, reminder["id"])

            self.assertEqual(removed["id"], reminder["id"])
            self.assertEqual(json.loads(reminders_path.read_text())["reminders"], [])
            self.assertIsNone(delete_reminder(reminders_path, reminder["id"]))

    def test_add_rejects_non_jst_and_past_datetimes(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            reminders_path.write_text('{"reminders": []}\n', encoding="utf-8")
            now = datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)

            for value in (
                "2026-10-25T10:00:00+00:00",
                "2026-10-25 09:00",
            ):
                with self.subTest(datetime=value):
                    with self.assertRaises(ValueError):
                        add_reminder(
                            reminders_path,
                            value,
                            123456,
                            "test reminder",
                            now=now,
                        )

    def test_csv_registration_appends_valid_rows_and_parses_mentions(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            reminders_path.write_text(
                '{"reminders": [{"id":"existing","datetime":"2026-10-25T12:00:00+09:00","channel_id":"123456","content":"existing"}]}\n',
                encoding="utf-8",
            )
            csv_text = (
                "datetime,channel_id,content,mention_users,mention_roles\n"
                "2026-10-25 10:00,123456,Test reminder,234567;345678,456789\n"
            )

            registered = register_reminders_csv(
                reminders_path,
                csv_text,
                allowed_channel_ids={123456},
                now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
            )

            stored = json.loads(reminders_path.read_text(encoding="utf-8"))["reminders"]
            self.assertEqual(len(stored), 2)
            self.assertEqual(stored[0]["id"], "existing")
            self.assertEqual(stored[1]["id"], registered[0]["id"])
            self.assertEqual(stored[1]["mention_users"], ["234567", "345678"])
            self.assertEqual(stored[1]["mention_roles"], ["456789"])

    def test_csv_registration_is_atomic_when_any_row_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            initial = '{"reminders": []}\n'
            reminders_path.write_text(initial, encoding="utf-8")
            csv_text = (
                "datetime,channel_id,content\n"
                "2026-10-25 10:00,123456,Valid\n"
                "2026-10-25 09:00,123456,Past\n"
            )

            with self.assertRaisesRegex(ValueError, "3行目"):
                register_reminders_csv(
                    reminders_path,
                    csv_text,
                    now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
                )

            self.assertEqual(reminders_path.read_text(encoding="utf-8"), initial)

    def test_csv_registration_rejects_channel_outside_allowed_guild(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            reminders_path.write_text('{"reminders": []}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "このサーバー"):
                register_reminders_csv(
                    reminders_path,
                    (
                        "datetime,channel_id,content\n"
                        "2026-10-25 10:00,123456,Reminder\n"
                    ),
                    allowed_channel_ids={999999},
                    now=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc),
                )

    def test_csv_template_has_expected_columns(self):
        template = create_reminder_csv_template().decode("utf-8-sig")
        self.assertEqual(
            template.strip(),
            "datetime,channel_id,content,mention_users,mention_roles",
        )

    async def test_due_reminder_is_sent_logged_and_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            log_path = Path(directory) / "reminder_log.jsonl"
            reminders_path.write_text(
                json.dumps(
                    {
                        "reminders": [
                            {
                                "id": "test-reminder",
                                "datetime": "2026-10-25T10:00:00+09:00",
                                "channel_id": "123456",
                                "content": "test notification",
                                "mention_users": ["234567"],
                                "mention_roles": ["345678"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            channel = Mock(spec=discord.abc.Messageable)
            channel.send = AsyncMock()
            client = Mock()
            client.get_channel.return_value = channel

            await process_due_reminders(
                client,
                reminders_path,
                log_path,
                now=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
            )

            channel.send.assert_awaited_once()
            message = channel.send.await_args.args[0]
            self.assertIn("<@234567>", message)
            self.assertIn("<@&345678>", message)
            allowed_mentions = channel.send.await_args.kwargs["allowed_mentions"]
            self.assertFalse(allowed_mentions.everyone)
            self.assertEqual(
                [user.id for user in allowed_mentions.users],
                [234567],
            )
            self.assertEqual(
                [role.id for role in allowed_mentions.roles],
                [345678],
            )
            self.assertEqual(json.loads(reminders_path.read_text())["reminders"], [])
            log_record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(log_record["status"], "sent")
            self.assertEqual(log_record["id"], "test-reminder")

    async def test_future_reminder_is_not_sent_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            log_path = Path(directory) / "reminder_log.jsonl"
            reminders_path.write_text(
                json.dumps(
                    {
                        "reminders": [
                            {
                                "id": "future-reminder",
                                "datetime": "2026-10-25T12:00:00+09:00",
                                "channel_id": "123456",
                                "content": "later",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            channel = Mock(spec=discord.abc.Messageable)
            channel.send = AsyncMock()
            client = Mock()
            client.get_channel.return_value = channel

            await process_due_reminders(
                client,
                reminders_path,
                log_path,
                now=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
            )

            channel.send.assert_not_awaited()
            self.assertEqual(len(json.loads(reminders_path.read_text())["reminders"]), 1)
            self.assertFalse(log_path.exists())

    async def test_failed_delivery_is_logged_and_kept_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            log_path = Path(directory) / "reminder_log.jsonl"
            reminders_path.write_text(
                json.dumps(
                    {
                        "reminders": [
                            {
                                "id": "retry-reminder",
                                "datetime": "2026-10-25T10:00:00+09:00",
                                "channel_id": "123456",
                                "content": "retry me",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            channel = Mock(spec=discord.abc.Messageable)
            channel.send = AsyncMock(
                side_effect=discord.HTTPException(
                    response=Mock(status=500, reason="test"),
                    message="temporary failure",
                )
            )
            client = Mock()
            client.get_channel.return_value = channel

            await process_due_reminders(
                client,
                reminders_path,
                log_path,
                now=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(len(json.loads(reminders_path.read_text())["reminders"]), 1)
            log_record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(log_record["status"], "failed")
            self.assertEqual(log_record["id"], "retry-reminder")

    async def test_sent_log_prevents_resending_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            reminders_path = Path(directory) / "reminders.json"
            log_path = Path(directory) / "reminder_log.jsonl"
            scheduled_at = "2026-10-25T10:00:00+09:00"
            reminders_path.write_text(
                json.dumps(
                    {
                        "reminders": [
                            {
                                "id": "already-sent",
                                "datetime": scheduled_at,
                                "channel_id": "123456",
                                "content": "do not duplicate",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                json.dumps(
                    {
                        "id": "already-sent",
                        "datetime": scheduled_at,
                        "status": "sent",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            client = Mock()

            await process_due_reminders(
                client,
                reminders_path,
                log_path,
                now=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
            )

            client.get_channel.assert_not_called()
            self.assertEqual(json.loads(reminders_path.read_text())["reminders"], [])


if __name__ == "__main__":
    unittest.main()
