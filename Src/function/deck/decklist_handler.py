from __future__ import annotations

import re
import tempfile
from datetime import timedelta, timezone
from pathlib import Path

import discord

import function.discord.message.send_message as send_message

CARD_LINE_PATTERN = re.compile(r"^[1-9]\d*\s+.+\s+\([^)]+\)\s+\S+$")
COMMANDER_HEADERS = {"commander", "統率者"}
DECK_HEADERS = {"deck", "デッキ"}
DECKLIST_RESPONSE = "デッキリストをテキストファイルで送信します。"
JST = timezone(timedelta(hours=9))


def _normalize_header(line: str) -> str:
    return line.strip().removesuffix(":").removesuffix("：").strip().casefold()


def _matches_flat_decklist(content: str) -> bool:
    commander_match = re.match(
        r"^\s*(?:commander|統率者)\s*[:：]?\s+",
        content,
        re.IGNORECASE,
    )
    if commander_match is None:
        return False

    deck_match = re.search(
        r"\s+(?:deck|デッキ)\s*[:：]?\s+",
        content[commander_match.end() :],
        re.IGNORECASE,
    )
    if deck_match is None:
        return False

    commander_end = commander_match.end() + deck_match.start()
    commander_line = content[commander_match.end() : commander_end].strip()
    deck_content = content[commander_match.end() + deck_match.end() :].strip()
    if not CARD_LINE_PATTERN.fullmatch(commander_line):
        return False

    entry_starts = [
        match.start()
        for match in re.finditer(r"(?<!\S)[1-9]\d*\s+", deck_content)
    ]
    if not entry_starts or entry_starts[0] != 0:
        return False

    boundaries = [*entry_starts, len(deck_content)]
    valid_starts = {len(deck_content)}
    for start in reversed(entry_starts):
        if any(
            end in valid_starts
            and CARD_LINE_PATTERN.fullmatch(deck_content[start:end].strip())
            for end in boundaries
            if end > start
        ):
            valid_starts.add(start)

    return 0 in valid_starts


def _parse_sectioned_decklist(content: str) -> tuple[str, bool] | None:
    lines = content.splitlines()
    first_section = next(
        (index for index, line in enumerate(lines) if line.strip()),
        None,
    )
    if first_section is None:
        return None

    first_header = _normalize_header(lines[first_section])
    commander_present = False
    if first_header in COMMANDER_HEADERS:
        section_index = next(
            (index for index in range(first_section + 1, len(lines)) if lines[index].strip()),
            None,
        )
        if section_index is None:
            return None

        if _normalize_header(lines[section_index]) in DECK_HEADERS:
            deck_index = section_index
        elif CARD_LINE_PATTERN.fullmatch(lines[section_index].strip()):
            commander_present = True
            deck_index = next(
                (index for index in range(section_index + 1, len(lines)) if lines[index].strip()),
                None,
            )
            if deck_index is None or _normalize_header(lines[deck_index]) not in DECK_HEADERS:
                return None
        else:
            return None
    elif first_header in DECK_HEADERS:
        deck_index = first_section
    else:
        return None

    deck_lines = [line.strip() for line in lines[deck_index + 1 :] if line.strip()]
    if not deck_lines or not all(
        CARD_LINE_PATTERN.fullmatch(line) for line in deck_lines
    ):
        return None

    return "\n".join([lines[deck_index].strip(), *deck_lines]), commander_present


def matches_decklist_format(content: str) -> bool:
    return (
        _parse_sectioned_decklist(content) is not None
        or _matches_flat_decklist(content)
    )


def _attachment_filename(message: discord.Message) -> str:
    display_name = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        message.author.display_name,
    ).rstrip(" .")
    if not display_name:
        display_name = "user"

    timestamp = message.created_at.astimezone(JST).strftime("%Y%m%d_%H%M%S")
    return f"{display_name}_{timestamp}.txt"


async def process_decklist_message(
    client: discord.Client,
    message: discord.Message,
) -> bool:
    if message.author.bot or not message.content:
        return False

    sectioned_decklist = _parse_sectioned_decklist(message.content)
    if sectioned_decklist is None and not _matches_flat_decklist(message.content):
        return False

    content = message.content
    if sectioned_decklist is not None and not sectioned_decklist[1]:
        content = sectioned_decklist[0]

    with tempfile.TemporaryDirectory(prefix="decklist-") as temp_dir:
        file_path = Path(temp_dir) / _attachment_filename(message)
        file_path.write_text(content, encoding="utf-8")
        await send_message.send_message_to_channel_with_file(
            client,
            message.channel.id,
            DECKLIST_RESPONSE,
            str(file_path),
        )

    return True
