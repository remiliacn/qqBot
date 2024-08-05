import sqlite3
from datetime import datetime
from json import dumps, loads
from os import getcwd
from re import findall
from time import time
from typing import List

from loguru import logger
from youtube_dl.utils import sanitize_filename

from Services.util.common_util import HttpxHelperClient, DiscordGroupNotification, DiscordMessageStatus, time_to_literal
from awesome.Constants.vtuber_function_constants import GPT_4_MODEL_NAME
from config import SUPER_USER, DISCORD_AUTH


class DiscordService:
    def __init__(self):
        self.headers = {
            'Authorization': DISCORD_AUTH,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                          ' AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/126.0.0.0 Safari/537.36'
        }
        self.database = sqlite3.connect(f'{getcwd()}/data/db/live_notification_data.db')
        self._init_database()
        self.client = HttpxHelperClient()

    def _init_database(self):
        self.database.execute(
            """
            create table if not exists discord_notification (
                channel_id varchar(200) unique on conflict ignore,
                is_enabled boolean,
                channel_name varchar(250) not null,
                last_updated_time integer,
                group_to_notify text
            )
            """
        )
        self.database.commit()

    def _retrieve_all_record_in_db(self):
        result = self.database.execute(
            """
            select * from discord_notification
            """
        ).fetchall()
        if result is None:
            return []

        return result

    def get_group_ids_for_notification(self, channel_id: str):
        data = self.database.execute(
            """
            select group_to_notify from discord_notification where channel_id = ?
            """, (channel_id,)
        ).fetchone()

        if data is None:
            return None

        return data if not isinstance(data, tuple) else data[0]

    async def _get_one_notification_data_from_db(self, streamer_name: str):
        data = self.database.execute(
            """
            select * from discord_notification where channel_name = ?
            """, (streamer_name,)
        ).fetchone()

        return data

    async def _check_if_notification_exist_in_db(self, streamer_name) -> bool:
        data = await self._get_one_notification_data_from_db(streamer_name)
        return data is not None

    async def add_discord_follows_to_db(self, channel_id: str, name: str, group_id: str, last_updated_time=0):
        notification_group = self.get_group_ids_for_notification(name)

        if await self._check_if_notification_exist_in_db(name):
            await self.update_streamer_data(name, channel_id, group_id)
            return

        if notification_group is not None:
            streamer_group_list = loads(notification_group)
        else:
            streamer_group_list = []

        streamer_group_list.append(group_id)
        streamer_group_list = list(set(streamer_group_list))
        self.database.execute(
            """
            insert or replace into discord_notification
                (channel_name, is_enabled, channel_id, last_updated_time, group_to_notify)
                values (?, ?, ?, ?, ?)
            """, (name, True, channel_id, last_updated_time, dumps(streamer_group_list))
        )

        self.database.commit()

    async def _get_the_latest_existing_discord_message(self, channel_id):
        data = self.database.execute(
            """
            select last_updated_time from discord_notification where channel_id = ?
            """, (channel_id,)
        ).fetchone()

        return data if not isinstance(data, tuple) else data[0]

    async def check_discord_updates(self) -> List[DiscordGroupNotification]:
        notification_list = self._retrieve_all_record_in_db()
        statuses = []
        for item in notification_list:
            # is enabled.
            if not item[1]:
                continue
            discord_status = await self._retrieve_latest_discord_channel_message(item[0])
            if discord_status.has_update:
                try:
                    chatgpt_message = await self._get_machine_translation_result(discord_status)
                    if chatgpt_message.status_code == 500:
                        raise ConnectionError
                    chatgpt_message = chatgpt_message.text
                    final_message = f'\n原文来自{discord_status.message}\n粗翻：\n{chatgpt_message}'
                    statuses.append(DiscordGroupNotification(
                        is_success=discord_status.is_success,
                        message=final_message,
                        has_update=discord_status.has_update,
                        group_to_notify=discord_status.group_to_notify,
                        channel_name=item[2],
                        is_edit=discord_status.is_edit,
                        channel_id=item[0]
                    ))
                except Exception as err:
                    logger.error(f'Failed to machine translate. {err.__class__}')
                    statuses.append(DiscordGroupNotification(
                        is_success=discord_status.is_success,
                        message=discord_status.message,
                        has_update=discord_status.has_update,
                        group_to_notify=discord_status.group_to_notify,
                        channel_name=item[2],
                        is_edit=discord_status.is_edit,
                        channel_id=item[0]
                    ))

        return statuses

    async def _get_machine_translation_result(self, discord_status):
        url = 'http://localhost:5001/chat'
        logger.info('Requesting machine translation for discord update.')
        chatgpt_message = await self.client.post(
            url,
            json={
                'message': 'Please help to translate the following message to Chinese, While translating,'
                           'please ignore and remove messges that in this pattern: `[CQ:.*?]` '
                           'in your response and only response with the result of the translation. '
                           "Do not translate name, and translate \"stream\" to 直播: \n\n"
                           + discord_status.message,
                'is_chat': False,
                'user': SUPER_USER,
                'model_name': GPT_4_MODEL_NAME
            },
            timeout=20.0
        )
        return chatgpt_message

    @staticmethod
    async def group_notification_to_literal_string(data: DiscordGroupNotification):
        return (f'刚刚{data.channel_name}{"发布了" if not data.is_edit else "更新了"}最新动态！\n'
                f'{data.message}')

    async def _retrieve_latest_discord_channel_message(self, channel_id: str) -> DiscordMessageStatus:
        if not channel_id.isdigit():
            return DiscordMessageStatus(False, 'Channel ID should be digit.')

        latest_timestamp = await self._get_the_latest_existing_discord_message(channel_id)
        if latest_timestamp is None:
            latest_timestamp = 0

        result = await self.client.get(
            f'https://discord.com/api/v9/channels/{channel_id}/messages?limit=5',
            headers=self.headers)
        discord_msg_result = result.json()[0]
        latest_msg_timestamp = discord_msg_result['timestamp']
        latest_msg_timestamp = int(datetime.fromisoformat(latest_msg_timestamp).timestamp())

        edited_msg_timestamp = discord_msg_result['edited_timestamp']
        edited_msg_timestamp = 0 if edited_msg_timestamp is None else int(
            datetime.fromisoformat(edited_msg_timestamp).timestamp())

        final_text = ''
        is_edit = False

        author_object = discord_msg_result['author']
        poster_name = author_object['username'] \
            if 'username' in author_object else \
            (author_object['global_name'] if 'global_name' in author_object else '??')

        if latest_msg_timestamp > latest_timestamp:
            discord_msg_parsed_result = await self._analyze_discord_message(discord_msg_result['content'])
            attachment_msg_parsed_result = await self._analyze_discord_attachments(discord_msg_result['attachments'])

            final_text = poster_name + ':\n' + discord_msg_parsed_result + '\n' + attachment_msg_parsed_result
            await self._update_previous_timestamp(channel_id, latest_msg_timestamp)

        if edited_msg_timestamp > latest_timestamp and edited_msg_timestamp > latest_msg_timestamp:
            discord_msg_parsed_result = await self._analyze_discord_message(discord_msg_result['content'])
            attachment_msg_parsed_result = await self._analyze_discord_attachments(discord_msg_result['attachments'])

            final_text = discord_msg_parsed_result + '\n' + attachment_msg_parsed_result
            is_edit = True
            await self._update_previous_timestamp(channel_id, edited_msg_timestamp)

        group_to_notify = self.get_group_ids_for_notification(channel_id)
        return DiscordMessageStatus(True, final_text, group_to_notify, True if final_text else False, is_edit=is_edit)

    async def update_streamer_data(self, channel_name: str, channel_id: str, group_id: str, is_enabled=True):
        group_ids = self.get_group_ids_for_notification(channel_name)
        if group_ids is not None:
            try:
                group_ids = loads(group_ids)
            except Exception as err:
                logger.error(f'Loads group id list from db failed. {err.__class__}')
                group_ids = []

        group_ids.append(group_id)
        group_ids = dumps(list(set(group_ids)))
        self.database.execute(
            """
            update discord_notification set channel_id = ?, group_to_notify = ?, is_enabled = ? where channel_name = ?
            """, (channel_id, group_ids, is_enabled, channel_name)
        )
        self.database.commit()

    @staticmethod
    async def _analyze_discord_message(discord_msg_result: str):
        discord_msg_result = (discord_msg_result.replace('[(', '')
                              .replace('])', '')
                              .replace('()', ''))
        special_message_data: List[str] = findall(r'<(.*?)>', discord_msg_result)
        replacement_dict = {}

        for message in special_message_data:
            if message.startswith('t') and message.endswith('F'):
                timestamp = message.replace('t:', '').replace(':F', '')
                if timestamp.isdigit():
                    dt = datetime.fromtimestamp(float(timestamp))
                    translated_timestamp = dt.strftime('%B %d, %Y')
                    replacement_dict[message] = translated_timestamp
            elif message.startswith('t') and message.endswith('R'):
                timestamp = message.replace('t:', '').replace(':R', '')
                if timestamp.isdigit():
                    time_until_that_timestamp = int(timestamp) - int(time())
                    replacement_dict[message] = f'{await time_to_literal(time_until_that_timestamp)}后'
            else:
                replacement_dict[message] = ''

        for key, item in replacement_dict.items():
            discord_msg_result = discord_msg_result.replace(f'<{key}>', item)

        return discord_msg_result.strip()

    async def _analyze_discord_attachments(self, attachments: List[dict]) -> str:
        orig_text = ''
        for attachment in attachments:
            file_type, file_extension = attachment['content_type'].split('/')
            placeholder_name = sanitize_filename(attachment['placeholder'])
            if file_type == 'image':
                file_name = f"{getcwd()}/data/bilibiliPic/{placeholder_name}.{file_extension}"

                await self.client.download(attachment['url'], file_name, headers=self.headers)
                orig_text += f'\n[CQ:image,file=file:///{file_name}]'

        return orig_text

    async def _update_previous_timestamp(self, channel_id: str, latest_msg_timestamp: int):
        self.database.execute(
            """
            update discord_notification set last_updated_time = ? where channel_id = ?
            """, (latest_msg_timestamp, channel_id)
        )
        self.database.commit()
