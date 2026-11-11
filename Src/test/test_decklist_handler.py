import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from event.on_message import on_message
from function.deck import decklist_handler


VALID_DECKLIST = """Commander
1 Yuriko, the Tiger's Shadow (FCA) 60

Deck
1 Ornithopter (BRR) 37
8 Island (NEO) 296
"""


class DecklistHandlerTests(unittest.IsolatedAsyncioTestCase):
    def test_matches_decklist_format(self):
        self.assertTrue(decklist_handler.matches_decklist_format(VALID_DECKLIST))

    def test_matches_single_line_decklist(self):
        content = (
            "Commander 1 Yuriko, the Tiger's Shadow (FCA) 60 "
            "Deck 1 Ornithopter (BRR) 37 8 Island (NEO) 296"
        )

        self.assertTrue(decklist_handler.matches_decklist_format(content))

    def test_matches_decklist_without_commander(self):
        contents = (
            "Commander\n\nDeck\n1 Island (NEO) 296\n",
            "Deck\n1 Island (NEO) 296\n",
        )

        for content in contents:
            with self.subTest(content=content):
                self.assertTrue(decklist_handler.matches_decklist_format(content))

    def test_rejects_non_decklist_message(self):
        self.assertFalse(decklist_handler.matches_decklist_format("hello"))
        self.assertFalse(
            decklist_handler.matches_decklist_format(
                "Commander\nNot a card\n\nDeck\n1 Card (SET) 1"
            )
        )

    async def test_processes_decklist_through_shared_file_sender(self):
        client = object()
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False, display_name="Yuriko"),
            content=VALID_DECKLIST,
            channel=SimpleNamespace(id=123),
            id=456,
            created_at=datetime(2026, 10, 29, 4, 39, 38, 123000, tzinfo=timezone.utc),
        )
        sender = AsyncMock()

        async def verify_attachment(*args):
            self.assertEqual(
                Path(args[3]).read_text(encoding="utf-8"),
                VALID_DECKLIST,
            )

        sender.side_effect = verify_attachment

        with patch.object(
            decklist_handler.send_message,
            "send_message_to_channel_with_file",
            sender,
        ):
            result = await decklist_handler.process_decklist_message(client, message)

        self.assertTrue(result)
        sender.assert_awaited_once()
        args = sender.await_args.args
        self.assertIs(args[0], client)
        self.assertEqual(args[1], 123)
        self.assertEqual(args[2], decklist_handler.DECKLIST_RESPONSE)
        self.assertEqual(Path(args[3]).name, "Yuriko_20261029_133938.txt")
        self.assertFalse(Path(args[3]).exists())

    async def test_attaches_only_deck_section_when_commander_is_missing(self):
        deck_section = "Deck\n1 Island (NEO) 296"
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False, display_name="Deck/User"),
            content=f"Commander\n\n{deck_section}\n",
            channel=SimpleNamespace(id=123),
            id=456,
            created_at=datetime(2026, 10, 29, 4, 39, 38, 123000, tzinfo=timezone.utc),
        )
        sender = AsyncMock()

        async def verify_attachment(*args):
            self.assertEqual(Path(args[3]).read_text(encoding="utf-8"), deck_section)

        sender.side_effect = verify_attachment

        with patch.object(
            decklist_handler.send_message,
            "send_message_to_channel_with_file",
            sender,
        ):
            result = await decklist_handler.process_decklist_message(object(), message)

        self.assertTrue(result)
        sender.assert_awaited_once()
        self.assertEqual(
            Path(sender.await_args.args[3]).name,
            "Deck_User_20261029_133938.txt",
        )

    async def test_ignores_bot_messages(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=True),
            content=VALID_DECKLIST,
        )

        with patch.object(
            decklist_handler.send_message,
            "send_message_to_channel_with_file",
            new_callable=AsyncMock,
        ) as sender:
            result = await decklist_handler.process_decklist_message(object(), message)

        self.assertFalse(result)
        sender.assert_not_awaited()

    async def test_on_message_routes_regular_decklist_messages(self):
        client = object()
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            guild=SimpleNamespace(id=789),
            channel=SimpleNamespace(id=123),
        )

        with patch.object(
            decklist_handler,
            "process_decklist_message",
            new_callable=AsyncMock,
            return_value=True,
        ) as processor, patch.object(
            on_message,
            "get_scenario_wait_type",
        ) as get_wait_type:
            await on_message.on_message_main(client, message)

        processor.assert_awaited_once_with(client, message)
        get_wait_type.assert_not_called()
