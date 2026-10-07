import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import AppCommandOptionType, app_commands

from event.on_message.command import slash_commands

HANDLER_MODULES = [
    name
    for name in dir(slash_commands)
    if isinstance(getattr(slash_commands, name), type(slash_commands))
    and getattr(getattr(slash_commands, name), "__name__", "").startswith("event.on_message.command.")
]


def _sample_value(parameter):
    kind = parameter.type
    if kind in (AppCommandOptionType.user, AppCommandOptionType.mentionable):
        return SimpleNamespace(mention="<@1>")
    if kind == AppCommandOptionType.channel:
        return SimpleNamespace(mention="<#1>")
    if kind == AppCommandOptionType.attachment:
        return MagicMock(spec=discord.Attachment)
    if kind == AppCommandOptionType.integer:
        return 1
    if kind == AppCommandOptionType.boolean:
        return True
    if kind == AppCommandOptionType.number:
        return 1.0
    if parameter.choices:
        return parameter.choices[0].value
    return "sample"


class AllSlashCommandsTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_slash_command_calls_its_handler_with_valid_arguments(self):
        client = discord.Client(intents=discord.Intents.none())
        tree = app_commands.CommandTree(client)
        slash_commands.register_slash_commands(tree)

        patched = {}
        for name in HANDLER_MODULES:
            module = getattr(slash_commands, name)
            if hasattr(module, "main"):
                patched[name] = patch.object(module, "main", autospec=True).start()
                self.addCleanup(patch.stopall)

        commands = [c for c in tree.walk_commands() if isinstance(c, app_commands.Command)]
        self.assertGreaterEqual(len(commands), 28)

        for command in commands:
            with self.subTest(command=command.qualified_name):
                for mock in patched.values():
                    mock.reset_mock()
                interaction = MagicMock()
                interaction.client = client
                interaction.response.defer = AsyncMock()
                interaction.response.send_message = AsyncMock()
                kwargs = {p.name: _sample_value(p) for p in command.parameters}
                await command.callback(interaction, **kwargs)

                if command.qualified_name == "help":
                    interaction.response.send_message.assert_awaited_once()
                    continue
                called = [n for n, m in patched.items() if m.await_count == 1]
                self.assertEqual(len(called), 1, f"{command.qualified_name}: handler call count")


if __name__ == "__main__":
    unittest.main()
