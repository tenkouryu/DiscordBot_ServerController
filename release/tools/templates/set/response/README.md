# Set Responses

Set commands return a CSV attachment based on the submitted input. Channel, member-role, and server-role results contain `result` and `reason` columns. Scenario registration is a batch operation; its overall result and reason are recorded on each data row.

These files are generated per request, retained in this folder, and also returned as Discord attachments. Generated CSV files are excluded from Git because they may contain server data.