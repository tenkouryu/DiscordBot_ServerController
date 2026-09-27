import csv

import discord
import function.discord.role.edit_roll as edit_roll
import function.discord.message.send_message as send_message
from function.file.template_output_service import (
	create_template_output_path,
	delete_template_output,
)
from function.security.permissions import can_manage_roles

"""
	サーバーロール一覧取得コマンドを処理する。

	export_roles_to_csv:
		サーバーのロール設定をCSVファイルへ出力する。

	main:
		ロール設定CSVを作成して送信する。
"""

def export_roles_to_csv(guild: discord.Guild, file_path: str) -> str:
	"""サーバーのロール設定を CSV ファイルに出力する。"""
	if guild is None:
		raise ValueError("サーバーが指定されていません。")

	role_settings = [
		edit_roll.get_role_settings(guild, role.name)
		for role in guild.roles
		if not role.is_default()
	]
	permission_names = sorted(
		{
			permission_name
			for settings in role_settings
			for permission_name in settings["permissions"]
		}
	)
	field_names = ["id", "name", "color", *permission_names]

	with open(file_path, "w", newline="", encoding="utf-8-sig") as csvfile:
		writer = csv.writer(csvfile)
		writer.writerow(field_names)
		for settings in role_settings:
			writer.writerow(
				[
					settings["id"],
					settings["name"],
					settings["color"],
					*[settings["permissions"].get(permission_name, False)
					  for permission_name in permission_names],
				]
			)

	return file_path


async def main(client: discord.Client, message: discord.Message) -> None:
	"""ロール設定を CSV に出力して、実行チャンネルへ送信する。"""
	if message.content.partition(" ")[2].strip() == "-h":
		await message.channel.send(
			"/server role get: サーバーのロール情報を CSV ファイルで取得します。"
		)
		return

	if not can_manage_roles(message.author):
		await message.channel.send('ロールを取得する権限がありません。')
		return

	file_path = create_template_output_path(
		"get/result",
		f"server_role_get_{message.guild.id}",
	)
	export_roles_to_csv(message.guild, str(file_path))
	try:
		await send_message.send_message_to_channel_with_file(
			client,
			message.channel.id,
			"サーバーのロール一覧を送信します。",
			str(file_path),
		)
	finally:
		delete_template_output(file_path)