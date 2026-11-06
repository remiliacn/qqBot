import mimetypes
import re
from datetime import datetime
from hashlib import sha1
from json import JSONDecodeError, dumps, loads
from os import path
from typing import Any, List, Optional
from urllib.parse import urlsplit

import aiosqlite
from loguru import logger
from nonebot.adapters.onebot.v11 import MessageSegment
from youtube_dl.utils import sanitize_filename

from Services.discord.discord_parser import discord_md_to_text
from Services.util.common_util import HttpxHelperClient
from awesome.Constants.path_constants import BILIBILI_PIC_PATH, DB_PATH
from config import DISCORD_AUTH
from model.common_model import DiscordMessageStatus, DiscordGroupNotification
from util.db_utils import fetch_one_or_default
from util.helper_util import construct_message_chain

mimetypes.add_type('image/webp', '.webp')

_IMAGE_EXTENSIONS = ('.gif', '.png', '.jpg', '.jpeg', '.webp', '.bmp')

_IMAGE_LINK_PATTERN = re.compile(
    r'(?P<md>\[(?P<label>[^\]]*)\]\((?P<md_url><?[^\s\)<>"]+>?)\))|(?P<raw><?(?P<raw_url>https?://[^\s<>"]+)>?)'
)


def _extract_image_link_candidates(text: str) -> list[tuple[str, str, str]]:
    candidates = []
    for match in _IMAGE_LINK_PATTERN.finditer(text):
        if match.group('md'):
            full_match = match.group('md')
            raw_url = match.group('md_url').strip('<>')
            label = match.group('label')
        else:
            full_match = match.group('raw')
            raw_url = match.group('raw_url').strip('<>')
            label = ''

        clean_url = raw_url.rstrip(')>.,;?!')
        try:
            url_path = urlsplit(clean_url).path.lower()
        except Exception:
            continue

        if url_path.endswith(_IMAGE_EXTENSIONS):
            candidates.append((full_match, clean_url, label))

    return candidates


def _get_image_download_headers(url: str, base_headers: Optional[dict[str, str]] = None) -> dict[str, str]:
    headers = {
        'User-Agent': (base_headers or {}).get(
            'User-Agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            ' AppleWebKit/537.36 (KHTML, like Gecko)'
            ' Chrome/126.0.0.0 Safari/537.36'
        )
    }
    netloc = urlsplit(url).netloc.lower()
    is_discord = (
        netloc == 'discord.com' or netloc.endswith('.discord.com') or
        netloc == 'discordapp.com' or netloc.endswith('.discordapp.com') or
        netloc == 'discordapp.net' or netloc.endswith('.discordapp.net')
    )
    if is_discord and base_headers and 'Authorization' in base_headers:
        headers['Authorization'] = base_headers['Authorization']
    return headers


async def _download_discord_image(
        url: str,
        client: HttpxHelperClient,
        headers: Optional[dict[str, str]] = None,
) -> Optional[str]:
    try:
        parsed_path = urlsplit(url).path
        base_name = path.basename(parsed_path) or 'image'
        base_root, _ = path.splitext(base_name)
        safe_base = sanitize_filename(base_root) or 'discord_img'
        unique_suffix = sha1(url.encode('utf-8')).hexdigest()[:8]
        target_file_name = path.join(BILIBILI_PIC_PATH, f"{safe_base}_{unique_suffix}")

        download_headers = _get_image_download_headers(url, headers)
        downloaded_path = await client.download(url, target_file_name, headers=download_headers)

        if downloaded_path and path.exists(downloaded_path) and path.getsize(downloaded_path) > 0:
            return downloaded_path

        return None
    except Exception as err:
        logger.warning(f"Exception downloading image from {url}: {err.__class__.__name__}")
        return None

_VTUBER_TRANSLATION_SYSTEM_PROMPT = """You are an expert translator specializing in Virtual YouTuber (VTuber) livestream announcements, Discord notifications, and fan community communications.

Translate English VTuber Discord announcements into natural, engaging Simplified Chinese suitable for VTuber fan groups and notification channels.

Guidelines:
1. Tone and Community Style:
   - Convey the streamer's personality, excitement, and emotional nuance naturally (friendly, energetic, cute, or casual).
   - Use authentic VTuber fan community phrasing (熟肉/通知组风格) rather than stiff or literal machine translation.

2. Terminology and Streaming Vocabulary:
   - "stream" / "streaming" -> 直播 / 开播
   - "collab" / "collaboration" -> 联动
   - "waiting room" -> 待机所 / 待机室
   - "singing stream" / "karaoke" -> 歌回 / 歌会
   - "endurance" / "endurance stream" / "marathon" -> 耐久直播 / 耐久回
   - "watchalong" / "watch party" -> 同步视听 / 同看
   - "outfit reveal" / "new outfit" -> 新衣回 / 新衣服披露
   - "schedule" -> 周表 / 直播日程
   - "POV" -> 视角

3. Preservation Rules (Do NOT translate or alter):
   - VTuber, talent, and human names (e.g. keep original names like Kiara, Nerissa, Fuwamoco, Biboo, etc.). TV show, movie, and game names are fine to translate to common Chinese titles or keep in English.
   - Discord mentions and role tags (e.g. @everyone, @here, <@123456>, <@&123456>).
   - Discord dynamic timestamps (e.g. <t:1700000000:R>, <t:1700000000:f>) and formatted timestamps.
   - URLs and links (YouTube, Twitch, X/Twitter, etc.).
   - Discord custom emojis (<:name:id>, <a:name:id>) and standard unicode emojis.
   - Discord markdown formatting (**bold**, *italics*, ~~strikethrough~~, > quotes, ||spoiler||).
   - Keep specific scheduled times and timezones (JST, PST, EST, UTC) clear and accurate.
   - If the message begins with a username or poster header (e.g. "Name:\\n"), preserve the name and structure.

4. Output Constraints:
   - Output ONLY the final Chinese translation.
   - Do NOT add any notes, thoughts, explanations, or prefixes (e.g. do not output "翻译：" or "ZH:").
   - Do NOT wrap the entire response in markdown code blocks.

Examples:

Source:
@everyone Going live in 15 minutes!
Tonight we are doing a Minecraft endurance collab with Nerissa!
Waiting room is open: https://youtube.com/watch?v=example
Translation:
@everyone 还有15分钟开播！
今晚要和 Nerissa 一起进行 Minecraft 耐久联动！
待机所已开启：https://youtube.com/watch?v=example

Source:
GUERRILLA! Unarchived singing stream starting soon!
No VOD, so make sure to come hang out!
Translation:
突击开播！不留档歌回马上开始！
本次直播不留回放，大家一定要来看哦！

Source:
Sorry guys, running about 10 minutes late due to audio setup issues!
Stream will start at 20:10 JST. See you soon!
Translation:
抱歉大家，因为音频设备调试会稍微推迟约10分钟！
直播将于日本时间 20:10 开始，待会儿见！
"""


class DiscordService:
    def __init__(self) -> None:
        self.headers = {
            'Authorization': DISCORD_AUTH,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                          ' AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/126.0.0.0 Safari/537.36'
        }
        self.db_file_path = path.join(DB_PATH, 'live_notification_data.db')
        self.client = HttpxHelperClient()

    @staticmethod
    async def _init_database(database: aiosqlite.Connection) -> None:
        await database.execute(
            """
            create table if not exists discord_notification
            (
                channel_id      varchar(200) unique on conflict ignore,
                is_enabled      boolean,
                channel_name    varchar(250) not null,
                last_updated_time integer,
                group_to_notify text
            )
            """
        )
        await database.commit()

    async def _fetchone(self, sql: str, params: tuple[Any, ...]) -> Optional[tuple[Any, ...]]:
        async with aiosqlite.connect(self.db_file_path) as database:
            await self._init_database(database)
            async with database.execute(sql, params) as cursor:
                return await cursor.fetchone()

    async def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        async with aiosqlite.connect(self.db_file_path) as database:
            await self._init_database(database)
            async with database.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

        return rows or []

    async def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        async with aiosqlite.connect(self.db_file_path) as database:
            await self._init_database(database)
            await database.execute(sql, params)
            await database.commit()

    async def _retrieve_all_record_in_db(self) -> list[tuple[Any, ...]]:
        return await self._fetchall(
            """
            select *
            from discord_notification
            """
        )

    async def _get_group_ids_for_notification_by_channel_id(self, channel_id: str) -> Optional[str]:
        data = await self._fetchone(
            """
            select group_to_notify
            from discord_notification
            where channel_id = ?
            """, (channel_id,)
        )

        if data is None:
            return None

        return data if not isinstance(data, tuple) else data[0]

    async def _get_group_ids_for_notification_by_channel_name(self, channel_name: str) -> Optional[str]:
        data = await self._fetchone(
            """
            select group_to_notify
            from discord_notification
            where channel_name = ?
            """, (channel_name,)
        )

        if data is None:
            return None

        return data if not isinstance(data, tuple) else data[0]

    async def _get_one_notification_data_from_db(self, streamer_name: str) -> Optional[tuple[Any, ...]]:
        return await self._fetchone(
            """
            select *
            from discord_notification
            where channel_name = ?
            """, (streamer_name,)
        )

    async def _check_if_notification_exist_in_db(self, streamer_name: str) -> bool:
        data = await self._get_one_notification_data_from_db(streamer_name)
        return data is not None

    async def add_discord_follows_to_db(
            self,
            channel_id: str,
            name: str,
            group_id: str,
            last_updated_time: int = 0,
    ) -> None:
        notification_group = await self._get_group_ids_for_notification_by_channel_name(name)

        if await self._check_if_notification_exist_in_db(name):
            await self.update_streamer_data(name, channel_id, group_id)
            return

        if notification_group is not None:
            try:
                streamer_group_list = loads(notification_group)
            except (JSONDecodeError, TypeError) as err:
                logger.error(f'Loads group id list from db failed. {err.__class__}')
                streamer_group_list = []
        else:
            streamer_group_list = []

        streamer_group_list.append(group_id)
        streamer_group_list = list(set(streamer_group_list))
        await self._execute(
            """
            insert or replace into discord_notification
                (channel_name, is_enabled, channel_id, last_updated_time, group_to_notify)
                values (?, ?, ?, ?, ?)
            """, (name, True, channel_id, last_updated_time, dumps(streamer_group_list))
        )

    async def check_discord_updates(self) -> List[DiscordGroupNotification]:
        notification_list = await self._retrieve_all_record_in_db()
        statuses: List[DiscordGroupNotification] = []
        for item in notification_list:
            channel_id = item[0]
            is_enabled = item[1]
            channel_name = item[2]
            last_updated_time = item[3]
            group_to_notify = item[4]

            if not is_enabled:
                continue

            discord_status = await self._retrieve_latest_discord_channel_message(
                channel_id,
                latest_timestamp=fetch_one_or_default((last_updated_time,), 0),
                group_to_notify=group_to_notify,
            )
            if discord_status.has_update:
                try:
                    chatgpt_message = await self._get_machine_translation_result(discord_status)
                    if chatgpt_message:
                        final_message = construct_message_chain(
                            '\n', discord_status.message, '\n粗翻：\n', chatgpt_message)
                    else:
                        final_message = construct_message_chain(discord_status.message)

                    statuses.append(DiscordGroupNotification(
                        is_success=discord_status.is_success,
                        message=final_message,
                        has_update=discord_status.has_update,
                        group_to_notify=discord_status.group_to_notify,
                        channel_name=channel_name,
                        is_edit=discord_status.is_edit,
                        channel_id=channel_id
                    ))
                except (ConnectionError, KeyError, ValueError, TypeError) as err:
                    logger.error(f'Failed to machine translate. {err.__class__}')
                    statuses.append(DiscordGroupNotification(
                        is_success=discord_status.is_success,
                        message=construct_message_chain(discord_status.message),
                        has_update=discord_status.has_update,
                        group_to_notify=discord_status.group_to_notify,
                        channel_name=channel_name,
                        is_edit=discord_status.is_edit,
                        channel_id=channel_id
                    ))

        return statuses

    @staticmethod
    async def _get_machine_translation_result(discord_status: DiscordMessageStatus) -> Optional[str]:
        logger.info('Requesting machine translation for discord update.')

        from Services import chatgpt_api
        from Services.chatgpt import ChatGPTRequestMessage

        message_text = '\n'.join([x.__str__() for x in discord_status.message if x.type == 'text'])

        content_lines = [
            line.strip() for line in message_text.splitlines()
            if line.strip() and not line.strip().endswith(':')
        ]
        if not content_lines:
            return None

        chatgpt_message = await chatgpt_api.chat(
            ChatGPTRequestMessage(
                message=message_text,
                is_chat=False,
                model_name='gpt-6-luna',
                force_no_web_search=True,
                context=_VTUBER_TRANSLATION_SYSTEM_PROMPT
            ))

        if chatgpt_message.is_success:
            return chatgpt_message.message

        return None

    @staticmethod
    async def group_notification_to_literal_string(data: DiscordGroupNotification) -> str:
        return (f'刚刚{data.channel_name}{"发布了" if not data.is_edit else "更新了"}最新动态！\n'
                f'{data.message}')

    @staticmethod
    def _parse_discord_iso_ts(raw_ts: Optional[str]) -> int:
        if not raw_ts:
            return 0

        normalized = raw_ts.replace('Z', '+00:00')
        try:
            return int(datetime.fromisoformat(normalized).timestamp())
        except ValueError as err:
            logger.error(f'Failed to parse discord timestamp. {err.__class__}')
            return 0

    async def _retrieve_latest_discord_channel_message(
            self,
            channel_id: str,
            latest_timestamp: Optional[int] = None,
            group_to_notify: Optional[str] = None,
    ) -> DiscordMessageStatus:
        if not channel_id.isdigit():
            return DiscordMessageStatus(False, [MessageSegment.text('Channel ID should be digit.')])

        if not DISCORD_AUTH:
            return DiscordMessageStatus(False)

        result = await self.client.get(
            f'https://discord.com/api/v9/channels/{channel_id}/messages?limit=5',
            headers=self.headers)

        final_message_segments: List[MessageSegment] = []

        try:
            discord_msg_result_all = result.json()[::-1]
        except (ValueError, TypeError) as err:
            logger.error(f'Failed to parse discord api response. {err.__class__}')
            return DiscordMessageStatus(False)

        is_edit = False

        resolved_latest_timestamp = (
            latest_timestamp
            if latest_timestamp is not None
            else await self._get_the_latest_existing_discord_message(channel_id)
        )

        for discord_msg_result in discord_msg_result_all:
            latest_msg_timestamp = self._parse_discord_iso_ts(discord_msg_result.get('timestamp'))
            edited_msg_timestamp = self._parse_discord_iso_ts(discord_msg_result.get('edited_timestamp'))

            author_object = discord_msg_result.get('author') or {}
            poster_name = author_object.get('username') or author_object.get('global_name') or '??'

            if edited_msg_timestamp > resolved_latest_timestamp and edited_msg_timestamp > latest_msg_timestamp:
                discord_msg_parsed_result = await self._analyze_discord_message(discord_msg_result.get('content', ''))
                attachment_msg_parsed_result = await self._analyze_discord_attachments(
                    discord_msg_result.get('attachments') or [])

                final_message_segments.append(MessageSegment.text(poster_name + ':\n'))
                final_message_segments += discord_msg_parsed_result
                final_message_segments.append(MessageSegment.text('\n'))
                final_message_segments += attachment_msg_parsed_result
                is_edit = True
                await self._update_previous_timestamp(channel_id, edited_msg_timestamp)
                resolved_latest_timestamp = max(resolved_latest_timestamp, edited_msg_timestamp)

            elif latest_msg_timestamp > resolved_latest_timestamp:
                discord_msg_parsed_result = await self._analyze_discord_message(discord_msg_result.get('content', ''))
                attachment_msg_parsed_result = await self._analyze_discord_attachments(
                    discord_msg_result.get('attachments') or [])

                final_message_segments.append(MessageSegment.text(poster_name + ':\n'))
                final_message_segments += discord_msg_parsed_result
                final_message_segments.append(MessageSegment.text('\n'))
                final_message_segments += attachment_msg_parsed_result
                await self._update_previous_timestamp(channel_id, latest_msg_timestamp)
                resolved_latest_timestamp = max(resolved_latest_timestamp, latest_msg_timestamp)

        resolved_group_to_notify = (
            group_to_notify
            if group_to_notify is not None
            else await self._get_group_ids_for_notification_by_channel_id(channel_id)
        )

        return DiscordMessageStatus(
            True, final_message_segments, resolved_group_to_notify,
            True if final_message_segments else False, is_edit=is_edit)

    async def update_streamer_data(
            self,
            channel_name: str,
            channel_id: str,
            group_id: str,
            is_enabled: bool = True,
    ) -> None:
        group_ids = await self._get_group_ids_for_notification_by_channel_name(channel_name)
        group_id_list: list[str]
        if group_ids is not None:
            try:
                group_id_list = loads(group_ids)
            except (JSONDecodeError, TypeError) as err:
                logger.error(f'Loads group id list from db failed. {err.__class__}')
                group_id_list = []
        else:
            group_id_list = []

        group_id_list.append(group_id)
        unique_group_ids = dumps(list(set(group_id_list)))
        await self._execute(
            """
            update discord_notification
            set channel_id      = ?,
                group_to_notify = ?,
                is_enabled      = ?
            where channel_name = ?
            """, (channel_id, unique_group_ids, is_enabled, channel_name)
        )

    async def _analyze_discord_message(
            self_or_content: Any,
            discord_msg_result: Optional[str] = None,
            client: Optional[HttpxHelperClient] = None,
            headers: Optional[dict[str, str]] = None,
    ) -> List[MessageSegment]:
        if isinstance(self_or_content, str) or self_or_content is None:
            raw_msg = self_or_content or ""
            active_client = client or HttpxHelperClient()
            active_headers = headers or {}
        else:
            raw_msg = discord_msg_result or ""
            active_client = client or getattr(self_or_content, 'client', None) or HttpxHelperClient()
            active_headers = headers or getattr(self_or_content, 'headers', None) or {}

        if not raw_msg or not raw_msg.strip():
            return []

        candidates = _extract_image_link_candidates(raw_msg)
        image_segments: List[MessageSegment] = []
        remaining_text = raw_msg

        for full_match, url, label in candidates:
            downloaded_file = await _download_discord_image(url, active_client, active_headers)
            if downloaded_file:
                image_segments.append(MessageSegment.image(downloaded_file))
                remaining_text = remaining_text.replace(full_match, label, 1)

        result_segments: List[MessageSegment] = []
        cleaned_text = re.sub(r'[ \t]+', ' ', remaining_text)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

        if cleaned_text:
            parsed_text = discord_md_to_text(cleaned_text)
            if parsed_text and parsed_text.strip():
                result_segments.append(MessageSegment.text(parsed_text))

        result_segments.extend(image_segments)
        return result_segments

    async def _analyze_discord_attachments(self, attachments: List[dict[str, Any]]) -> List[MessageSegment]:
        orig_text: List[MessageSegment] = []
        for attachment in attachments:
            content_type = attachment.get('content_type')
            if not content_type or '/' not in content_type:
                continue

            file_type, _ = content_type.split('/', 1)
            if file_type != 'image':
                continue

            placeholder = attachment.get('placeholder') or attachment.get('filename') or 'image'
            placeholder_name = sanitize_filename(placeholder)
            file_name = path.join(BILIBILI_PIC_PATH, placeholder_name)

            url = attachment.get('url')
            if not url:
                continue

            file_name = await self.client.download(url, file_name, headers=self.headers)
            if file_name and path.exists(file_name):
                orig_text.append(MessageSegment.image(file_name))

        return orig_text

    async def _get_the_latest_existing_discord_message(self, channel_id: str) -> int:
        data = await self._fetchone(
            """
            select last_updated_time
            from discord_notification
            where channel_id = ?
            """, (channel_id,)
        )

        return fetch_one_or_default(data, 0)

    async def _update_previous_timestamp(self, channel_id: str, latest_msg_timestamp: int) -> None:
        await self._execute(
            """
            update discord_notification
            set last_updated_time = ?
            where channel_id = ?
            """, (latest_msg_timestamp, channel_id)
        )

    async def get_group_ids_for_notification(self, channel_id: str) -> Optional[str]:
        return await self._get_group_ids_for_notification_by_channel_id(channel_id)
