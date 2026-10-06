# Set Input CSV

CSV files in this folder are input templates or examples for Set commands.

- `channel_template.csv`: `/channel set` (optional `user_1`, `user_2`, ... columns accept Discord usernames for additional channel access)
- `member_role_template.csv`: `/member role set` (uses `ユーザーID` first, then `ユーザー名`, then `表示名`; supports multiple `ロールN` columns)
- `server_role_template.csv`: `/server role set`
- `scenario_template.csv` and `team_match_scenario.csv`: `/scenario set`

Set result CSVs are generated per request, stored under `../response/`, and returned as Discord attachments.