import asyncio
import sqlite3
from json import dumps, loads
from os import getcwd
from time import time
from typing import Union, List

from loguru import logger

from Services.util.common_util import HttpxHelperClient, OptionalDict


class DynamicNotificationData:
    def __init__(self, name: str, dynamic_content: str):
        self.name = name
        self.dynamic_content = dynamic_content


class LiveNotificationData:
    def __init__(self, streamer_name, is_live, stream_title='', stream_thumbnail='', stream_live_time='', room_id='',
                 tags=''):
        self.streamer_name = streamer_name
        self.is_live = is_live
        self.stream_title = stream_title
        self.stream_thumbnail = stream_thumbnail
        self.stream_live_time = stream_live_time
        self.room_id = room_id
        self.live_change_status = '开播啦'
        self.tags = tags

    def set_live_change_status(self, status):
        self.live_change_status = status


class LiveNotification:
    def __init__(self):
        self.live_database = sqlite3.connect(f'{getcwd()}/data/db/live_notification_data.db')
        self.bilibili_live_check_url = 'https://api.live.bilibili.com/room/v1/Room/get_info?room_id='
        self._init_database()

    def _init_database(self):
        self.live_database.execute(
            """
            create table if not exists live_notification_bilibili (
                name text unique on conflict ignore,
                isEnabled boolean,
                uid varchar(200),
                last_checked_date varchar(200),
                last_record_live_status boolean,
                group_to_notify text
            )
            """
        )
        self.live_database.commit()

    async def _get_one_notification_data_from_db(self, streamer_name: str):
        data = self.live_database.execute(
            """
            select * from live_notification_bilibili where name = ?
            """, (streamer_name,)
        ).fetchone()

        return data

    async def stop_live_follow(self, streamer_name):
        logger.info(f'Received request to stop follow for {streamer_name}')
        if await self._check_if_notification_exist_in_db(streamer_name):
            data = await self._get_one_notification_data_from_db(streamer_name)
            uid = data[2]
            group_to_notify = data[-1]
            logger.info(f'Data found: uid: {uid}, groups: {group_to_notify}')

            await self.update_streamer_data(streamer_name, uid, group_to_notify, False)

    async def _check_if_notification_exist_in_db(self, streamer_name) -> bool:
        data = await self._get_one_notification_data_from_db(streamer_name)
        return data is not None

    def get_group_ids_for_streamer(self, name: str):
        data = self.live_database.execute(
            """
            select group_to_notify from live_notification_bilibili where name = ?
            """, (name,)
        ).fetchone()

        if data is None:
            return None

        return data if not isinstance(data, tuple) else data[0]

    async def update_streamer_data(self, name: str, uid: str, group_id: str, is_enabled=True):
        group_ids = self.get_group_ids_for_streamer(name)
        if group_ids is not None:
            try:
                group_ids = loads(group_ids)
            except Exception as err:
                logger.error(f'Loads group id list from db failed. {err.__class__}')
                group_ids = []

        group_ids.append(group_id)
        group_ids = dumps(list(set(group_ids)))
        self.live_database.execute(
            """
            update live_notification_bilibili set uid = ?, group_to_notify = ?, isEnabled = ? where name = ?
            """, (uid, group_ids, is_enabled, name)
        )
        self.live_database.commit()

    async def add_data_to_bilibili_notify_database(self, name: str, uid: str, group_id: str):
        streamer_groups = self.get_group_ids_for_streamer(name)

        if await self._check_if_notification_exist_in_db(name):
            await self.update_streamer_data(name, uid, group_id)
            return

        if streamer_groups is not None:
            streamer_group_list = loads(streamer_groups)
        else:
            streamer_group_list = []

        streamer_group_list.append(group_id)
        streamer_group_list = list(set(streamer_group_list))
        self.live_database.execute(
            """
            insert or replace into live_notification_bilibili
                (name, isEnabled, uid, last_checked_date, last_record_live_status, group_to_notify)
                values (?, ?, ?, ?, ?, ?)
            """, (name, True, uid, time(), False, dumps(streamer_group_list))
        )

        self.live_database.commit()

    async def update_live_status(self, streamer_name: str, status: Union[int, bool]):
        self.live_database.execute(
            """
            update live_notification_bilibili 
            set last_checked_date = ?, last_record_live_status = ? 
            where name = ?
            """, (time(), status, streamer_name)
        )
        self.live_database.commit()

    @staticmethod
    async def convert_live_data_to_string(data: LiveNotificationData) -> str:
        response = f'{data.streamer_name}{data.live_change_status}\n'
        if data.is_live:
            response += f'直播标题：{data.stream_title}\n' \
                        f'开播时间：{data.stream_live_time}\n'
            response += f'[CQ:image,file=file:///{data.stream_thumbnail}]\n' if data.stream_thumbnail else ''
            response += f'直播标签：{data.tags}'

        return response

    async def check_if_live(self, room_id: str, streamer_name: str) -> LiveNotificationData:
        logger.info(f'Checking live stat for {streamer_name}, room id: {room_id}')
        url = self.bilibili_live_check_url + room_id
        client = HttpxHelperClient()
        data_response_client = await client.get(url, headers={
            'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/84.0.4147.125 Safari/537.36'
        })
        data_response_json = data_response_client.json()
        is_live = OptionalDict(data_response_json).map('data') \
            .map('live_status') \
            .or_else(0)

        if not is_live:
            logger.info(f'{streamer_name} is not live.')
            return LiveNotificationData(
                streamer_name,
                False,
                room_id=room_id
            )

        stream_title = OptionalDict(data_response_json).map('data') \
            .map('title') \
            .or_else('未知')
        thumbnail_url = OptionalDict(data_response_json) \
            .map('data') \
            .map('user_cover') \
            .or_else(None)
        if thumbnail_url is not None:
            stream_thumbnail_filename = f'{getcwd()}/data/bilibiliPic/{thumbnail_url.split("/")[-1]}'
            await client.download(thumbnail_url, file_name=stream_thumbnail_filename)
        else:
            stream_thumbnail_filename = ''

        return LiveNotificationData(
            streamer_name,
            True,
            stream_title,
            stream_thumbnail_filename,
            OptionalDict(data_response_json).map('data').map('live_time').or_else('未知'),
            room_id,
            OptionalDict(data_response_json).map('data').map('tags').or_else('')
        )

    async def check_live_bilibili(self) -> List[LiveNotificationData]:
        user_needs_to_be_checked = self.live_database.execute(
            """
            select * from live_notification_bilibili
            """
        ).fetchall()

        live_data_list = []

        for live_data in user_needs_to_be_checked:
            streamer_name = live_data[0]
            is_enabled = live_data[1]
            room_id = live_data[2]
            last_record_state = live_data[4]

            if not is_enabled:
                logger.info(f'{streamer_name} is disable to send notification.')
                continue

            notify_data = await self.check_if_live(room_id, streamer_name)
            if last_record_state != notify_data.is_live:
                if notify_data.is_live:
                    notify_data.set_live_change_status('开播啦！')
                    live_data_list.append(notify_data)
                else:
                    notify_data = LiveNotificationData('糖糖', False)
                    notify_data.set_live_change_status('下播啦！')
                    live_data_list.append(notify_data)

                await self.update_live_status(streamer_name, notify_data.is_live)

        return live_data_list


class BilibiliDynamicNotifcation(LiveNotification):
    def __init__(self):
        super().__init__()
        self.dynamic_url = f'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?offset=&host_mid='
        self.TEXT_DYNAMIC_TYPE = 'RICH_TEXT_NODE_TYPE_TEXT'
        self.EMOJI_DYNAMIC_TYPE = 'RICH_TEXT_NODE_TYPE_EMOJI'
        self.AT_DYNAMIC_TYPE = 'RICH_TEXT_NODE_TYPE_AT'
        self.LIVESTREAM_DYNAMIC_TYPE = 'DYNAMIC_TYPE_LIVE_RCMD'
        self.VIDEO_DYNAMIC_TYPE = 'MAJOR_TYPE_ARCHIVE'
        self._init_database()

    def _init_database(self):
        self.live_database.execute(
            """
            create table if not exists dynamic_notification_bilibili (
                name text not null unique on conflict ignore,
                isEnabled boolean not null,
                mid text not null,
                last_dynamic_id var(255) not null,
                dynamic_time var(100) not null,
                group_to_notify text not null
            )
            """
        )
        self.live_database.commit()

    async def stop_notification_for_someone(self, name: str):
        self.live_database.execute(
            """
            update dynamic_notification_bilibili set isEnabled = ? where name = ?
            """, (False, name)
        )
        self.live_database.commit()

    async def add_to_dynamic_notification_queue(self, name: str, mid: str, group_id: Union[str, int]):
        group_ids = await self.get_group_to_notify(name)
        should_update = False
        if group_ids is not None:
            should_update = True
            group_ids = group_ids
        else:
            group_ids = []

        group_ids.append(group_id)
        group_ids = list(set(group_ids))
        if not should_update:
            self.live_database.execute(
                """
                insert or replace into dynamic_notification_bilibili
                 (name, isEnabled, mid, last_dynamic_id, dynamic_time, group_to_notify)
                 VALUES (?, ?, ?, ?, ?, ?)
                """, (name, True, mid, '0', '0', dumps(group_ids))
            )
            self.live_database.commit()
        else:
            self.live_database.execute(
                """
                update dynamic_notification_bilibili set group_to_notify = ?, isEnabled = 1 where name = ?
                """, (dumps(group_ids), name)
            )

    async def get_group_to_notify(self, name) -> Union[List[str], None]:
        data = self.live_database.execute(
            """
            select group_to_notify from dynamic_notification_bilibili where name = ?
            """, (name,)
        ).fetchone()

        return loads(data) if isinstance(data, str) else (loads(data[0]) if data is not None else None)

    async def update_latest_dynamic_id_for_user(self, name, dynamic_id, dynamic_time):
        self.live_database.execute(
            """
            update dynamic_notification_bilibili set last_dynamic_id = ?, dynamic_time = ? where name = ?
            """, (dynamic_id, dynamic_time, name)
        )
        self.live_database.commit()

    async def fetch_bilibili_newest_dynamic_for_up(self, name) -> Union[None, DynamicNotificationData]:
        user_needs_to_be_checked = self.live_database.execute(
            """
            select * from dynamic_notification_bilibili where name = ?
            """, (name,)
        ).fetchone()

        client = HttpxHelperClient()
        if user_needs_to_be_checked is not None:
            user_name = user_needs_to_be_checked[0]
            is_enabled = user_needs_to_be_checked[1]
            if not is_enabled:
                return None

            mid = user_needs_to_be_checked[2]
            last_dynamic_id = user_needs_to_be_checked[3]
            last_check_dynamic_time = int(user_needs_to_be_checked[4])

            dynamic_response = await client.get(
                self.dynamic_url + mid + f'&_={int(time())}',
                headers={
                    'Cookie': 'SESSDATA=xie_xie_bilibili.com',
                    'User-Agent': 'Mozilla/5.0',
                })
            dynamic_json = dynamic_response.json()
            for item in OptionalDict(dynamic_json).map('data').map('items').or_else([]):
                modules = OptionalDict(item).map('modules').or_else({})
                module_tag = OptionalDict(modules).map('module_tag').map('text').or_else('')
                if module_tag == '置顶':
                    continue

                dynamic_id = OptionalDict(item).map('id_str').or_else('')
                dynamic_time = OptionalDict(modules).map('module_author').map('pub_ts').or_else(0)
                dynamic_type = OptionalDict(item).map('type').or_else('')
                if dynamic_type == self.LIVESTREAM_DYNAMIC_TYPE:
                    continue

                # Reverted to one of the past dynamic for some reasons
                # Possibly because a dynamic being deleted or revoked.
                if dynamic_time <= last_check_dynamic_time:
                    break

                # Dynamic update is up-to-date.
                if dynamic_id == str(last_dynamic_id):
                    break

                orig_text = await self._analyze_dynamic(item)
                await self.update_latest_dynamic_id_for_user(user_name, dynamic_id, str(dynamic_time))
                return DynamicNotificationData(user_name, orig_text)

        return None

    async def _analyze_dynamic(self, item: dict):
        dynamic_module = OptionalDict(item).map('modules').map('module_dynamic').or_else({})
        rich_text_node = OptionalDict(dynamic_module).map('desc').map('rich_text_nodes').or_else([])
        orig_text = await self._fetch_content_in_text_node(rich_text_node)
        possible_node_type = OptionalDict(dynamic_module).map('major').map('type').or_else('')
        if possible_node_type == self.VIDEO_DYNAMIC_TYPE:
            orig_text += await self._analyze_video_dynamic_content(
                OptionalDict(dynamic_module).map('major')
                .map('archive')
                .or_else({}))

        orig_data = OptionalDict(item).map('orig').map('modules').map('module_dynamic').or_else({})
        orig_data_draw = OptionalDict(dynamic_module).map('major').map('draw').or_else({})
        if orig_data_draw:
            orig_text += '\n附图：' + await self._fetch_draw_from_dynamic(orig_data_draw)
        if orig_data:
            orig_text += '\n其他内容：\n' + await self._fetch_content_in_orig_node(orig_data)

        return orig_text

    @staticmethod
    async def construct_string_from_data(data: DynamicNotificationData):
        return f'{data.name}发新动态啦~\n\n' \
               f'{data.dynamic_content}'

    @staticmethod
    async def _fetch_draw_from_dynamic(orig_draw_node):
        draw_id = OptionalDict(orig_draw_node).map('id').or_else('')
        if not draw_id:
            return ''

        client = HttpxHelperClient()
        orig_text = ''
        for idx, item in enumerate(OptionalDict(orig_draw_node).map('items').or_else([])):
            file_name = f"{getcwd()}/data/bilibiliPic/{draw_id}_{idx}.jpg"
            await client.download(item['src'], file_name)
            orig_text += f'\n[CQ:image,file=file:///{file_name}]'

        return orig_text

    async def _fetch_content_in_text_node(self, rich_text_node):
        orig_text = ''
        for text_node in rich_text_node:
            orig_text += OptionalDict(text_node).map('orig_text').or_else('')
            node_type = OptionalDict(text_node).map('type').or_else('')
            if node_type == self.AT_DYNAMIC_TYPE:
                at_text = OptionalDict(text_node).map('orig_text').or_else('')
                orig_text += '@' if '@' not in at_text else '' \
                                                            + OptionalDict(text_node).map('orig_text').or_else('') + ' '
            elif node_type == self.EMOJI_DYNAMIC_TYPE:
                file_name = f"{getcwd()}/data/bilibiliPic/" \
                            f"{OptionalDict(text_node).map('emoji').map('text').or_else(str(time()))}.jpg"
                file_url = OptionalDict(text_node).map('emoji').map('icon_url').or_else('')
                if file_url:
                    client = HttpxHelperClient()
                    await client.download(file_url, file_name)
                orig_text += f'[CQ:image,file=file:///{file_name}]\n'

        return orig_text

    async def _fetch_content_in_orig_node(self, orig_data):
        rich_text_node = OptionalDict(orig_data) \
            .map('desc') \
            .map('rich_text_nodes') \
            .or_else([])
        orig_text = await self._fetch_content_in_text_node(rich_text_node)
        pic = OptionalDict(orig_data).map('major').map('draw').or_else({})
        archive = OptionalDict(orig_data).map('major').map('archive').or_else({})
        if pic:
            pic_id = pic['id']
            files = pic['items']
            for idx, file in enumerate(files):
                file_name = f"{getcwd()}/data/bilibiliPic/{pic_id}_{idx}.jpg"
                client = HttpxHelperClient()
                await client.download(file['src'], file_name)
                orig_text += f'\n[CQ:image,file=file:///{file_name}]'

        if archive:
            bvid = archive['bvid']
            forwarded_video_cover = f"{getcwd()}/data/bilibiliPic/{bvid}.jpg"
            client = HttpxHelperClient()
            await client.download(archive['cover'], forwarded_video_cover)

            orig_text += f'\n转发视频标题：{archive["title"]}\n' \
                         f'转发视频bvid：{bvid}\n' \
                         f'[CQ:image,file=file:///{forwarded_video_cover}]'

        return orig_text

    async def fetch_all_dynamic_updates(self):
        datas = self.live_database.execute(
            """
            select * from dynamic_notification_bilibili
            """
        ).fetchall()

        notify_list = []
        for data in datas:
            name, is_enabled, _, _, _, _ = data
            if is_enabled:
                dynamic_info = await self.fetch_bilibili_newest_dynamic_for_up(name)
                if dynamic_info is not None:
                    notify_list.append(dynamic_info)

        return notify_list

    @staticmethod
    async def _analyze_video_dynamic_content(archive_object):
        if not archive_object:
            return

        video_cover = OptionalDict(archive_object).map('cover').or_else('')
        bvid = OptionalDict(archive_object).map('bvid').or_else(str(time()))
        file_name = f"{getcwd()}/data/bilibiliPic/{bvid}.jpg"
        if video_cover:
            client = HttpxHelperClient()
            await client.download(video_cover, file_name)

        return f'发布了新视频：\n' \
               f'标题：{OptionalDict(archive_object).map("title").or_else("未知")}\n' \
               f'bvid：{bvid}\n' \
               f'[CQ:image,file=file:///{file_name}]\n'


async def main():
    d = BilibiliDynamicNotifcation()
    await d.add_to_dynamic_notification_queue('话梅糖', '3493264923560048', '212345')
    dd = await d.fetch_all_dynamic_updates()
    for ddd in dd:
        if ddd is not None:
            print(await d.construct_string_from_data(ddd))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
