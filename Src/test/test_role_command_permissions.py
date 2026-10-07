import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from discord import app_commands

from event.on_message.command.channel import create as channel_create
from event.on_message.command.channel import get as channel_get
from event.on_message.command.channel import move as channel_move
from event.on_message.command.channel import set as channel_set
from event.on_message.command.member import role_get as member_role_get
from event.on_message.command.server import role_get as server_role_get
from event.on_message.command.slash_commands import _InteractionMessage, register_slash_commands
from function.security.permissions import can_manage_channels, can_manage_roles


class RoleCommandPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_member_role_get_denies_without_manage_roles(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            author=SimpleNamespace(
                guild_permissions=SimpleNamespace(
                    manage_roles=False,
                    administrator=False,
                ),
            ),
            channel=channel,
            content="/member_role_get example",
            mentions=[],
        )

        await member_role_get.main(message)

        channel.send.assert_awaited_once_with(
            "メンバーのロールを取得する権限がありません。"
        )

    async def test_server_role_get_denies_without_manage_roles(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            author=SimpleNamespace(
                guild_permissions=SimpleNamespace(
                    manage_roles=False,
                    administrator=False,
                ),
            ),
            channel=channel,
            content="/server_role_get",
        )

        await server_role_get.main(None, message)

        channel.send.assert_awaited_once_with("ロールを取得する権限がありません。")

    async def test_interaction_message_author_is_invoking_user(self):
        user = object()
        interaction = SimpleNamespace(user=user, channel=None)

        message = _InteractionMessage(interaction, "/server_role_get")

        self.assertIs(message.author, user)

    async def test_server_role_get_slash_command_passes_client_to_handler(self):
        client = discord.Client(intents=discord.Intents.none())
        tree = app_commands.CommandTree(client)
        register_slash_commands(tree)
        server = tree.get_command("server")
        role = server.get_command("role")
        command = role.get_command("get")
        interaction = SimpleNamespace(
            client=client,
            user=object(),
            channel=None,
            response=SimpleNamespace(defer=AsyncMock()),
        )

        with patch.object(server_role_get, "main", new_callable=AsyncMock) as handler:
            await command.callback(interaction)

        handler.assert_awaited_once()
        args = handler.await_args.args
        self.assertIs(args[0], client)
        self.assertEqual(args[1].content, "/server_role_get")

    def test_administrator_can_manage_roles(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(
                manage_roles=False,
                administrator=True,
            ),
        )

        self.assertTrue(can_manage_roles(member))

    def test_administrator_can_manage_channels(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(
                manage_channels=False,
                administrator=True,
            ),
        )

        self.assertTrue(can_manage_channels(member))

    async def test_channel_commands_deny_without_manage_channels(self):
        channel = SimpleNamespace(send=AsyncMock())
        message = SimpleNamespace(
            author=SimpleNamespace(
                guild_permissions=SimpleNamespace(
                    manage_channels=False,
                    administrator=False,
                ),
            ),
            channel=channel,
            content="/channel command",
        )

        for handler in (channel_create, channel_move, channel_set, channel_get):
            with self.subTest(command=handler.__name__):
                channel.send.reset_mock()
                await handler.main(message)
                channel.send.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()