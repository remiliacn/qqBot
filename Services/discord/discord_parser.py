from datetime import datetime
from functools import lru_cache
from os import path
from re import compile as re_compile, sub
from subprocess import run, TimeoutExpired, CalledProcessError

from loguru import logger

_TS_PATTERN = re_compile(r"<t:(\d+)(?::\w+)?>")
_MENTION_PATTERN = re_compile(r"<[@#&]?\d+>")
_MARKDOWN_PATTERN = re_compile(r"\*\*|__|\*|_|`{1,3}|~~")

_DISCORD_PARSER_PATH = path.join(path.dirname(__file__), "discord_parse.js")


def _fallback_parser(msg: str) -> str:
    def replace_timestamp(match):
        try:
            timestamp = int(match.group(1))
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError) as err:
            logger.error(f"Failed to parse timestamp: {err.__class__.__name__}")
            return ""

    # Handle timestamps
    msg = _TS_PATTERN.sub(replace_timestamp, msg)

    msg = _MENTION_PATTERN.sub("", msg)

    # Remove custom and animated emojis: <:name:id> or <a:name:id>
    msg = sub(r"<a?:\w+:\d+>", "", msg)

    # Remove Markdown formatting
    msg = _MARKDOWN_PATTERN.sub("", msg)

    # Convert links [text](url) or [text](<url>) to text(url) format
    # But remove @ from [@username](<url>) format
    msg = sub(r"\[@([^]]+)\]\(<[^>]+>\)", r"\1", msg)
    msg = sub(r"\[#([^]]+)\]\(<[^>]+>\)", r"#\1", msg)
    msg = sub(r"\[([^]]+)\]\(<([^>]+)>\)", r"\1(\2)", msg)
    msg = sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1(\2)", msg)

    # Collapse multiple spaces but preserve newlines
    msg = sub(r"[ \t]+", " ", msg)

    return msg.strip()


@lru_cache(maxsize=512)
def discord_md_to_text(msg: str) -> str:
    if not msg or not msg.strip():
        return msg

    if not path.exists(_DISCORD_PARSER_PATH):
        logger.warning(
            f"Discord parser not found at {_DISCORD_PARSER_PATH}, using fallback parser"
        )
        return _fallback_parser(msg)

    try:
        result = run(
            ["node", _DISCORD_PARSER_PATH, msg],
            capture_output=True,
            text=True,
            timeout=3,
            encoding="utf-8",
        )

        if result.returncode != 0:
            logger.error(
                f"Discord parser failed with return code {result.returncode}: {result.stderr}"
            )
            return _fallback_parser(msg)

        parsed = result.stdout.strip()
        if not parsed:
            logger.warning("Discord parser returned empty output, using fallback")
            return _fallback_parser(msg)

        return parsed

    except TimeoutExpired:
        logger.error("Discord parser timed out, using fallback")
        return _fallback_parser(msg)

    except FileNotFoundError:
        logger.error("Node.js not found, using fallback parser")
        return _fallback_parser(msg)

    except CalledProcessError as err:
        logger.error(f"Discord parser error: {err.__class__.__name__}")
        return _fallback_parser(msg)

    except (OSError, UnicodeDecodeError, TypeError) as err:
        logger.error(f"Unexpected error in discord parser: {err.__class__.__name__}")
        return _fallback_parser(msg)


def clear_parser_cache() -> None:
    discord_md_to_text.cache_clear()
