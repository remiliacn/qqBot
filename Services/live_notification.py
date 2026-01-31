import codecs
import os
import pickle
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from json import dumps, loads
from os import getcwd, path
from sqlite3 import connect
from subprocess import Popen
from time import time, time_ns
from typing import Union, List, Dict, Tuple
from uuid import uuid1

from aiohttp import ClientSession
from async_lru import alru_cache
from nonebot.adapters.onebot.v11 import MessageSegment, Message
from nonebot.log import logger
from wordcloud import WordCloud

from Services.get_bvid import update_buvid_params
from Services.util import global_httpx_client
from Services.util.common_util import OptionalDict
from awesome.Constants.path_constants import BILIBILI_PIC_PATH
from config import DANMAKU_PROCESS
from util.helper_util import construct_message_chain


@dataclass
class LivestreamDanmakuData:
    danmaku_frequency_dict: Dict = None
    danmaku_count: int = 0
    qq_group_dumped: str = ''
    gift_received_count: int = 0
    like_received_count: int = 0
    highest_rank: int = 999
    gift_total_price: float = 0
    new_captains: int = 0
    top_crazy_timestamps: List[str] = field(default_factory=list)
    danmaku_analyze_graph: str = ''


def _parse_line(line: str) -> Tuple[int, str, str, float]:
    parts: list[str] = line.strip().split()

    guard_level_str: str = parts[0]
    match guard_level_str:
        case '提督':
            gd_lvl = 2
        case '总督':
            gd_lvl = 1
        case _:
            gd_lvl = 3

    user_id: str = parts[1]
    # onsail time + 31 days.
    ts: float = datetime.fromisoformat(parts[-1]).timestamp() + 60 * 60 * 24 * 31
    uname: str = " ".join(parts[2:-1])

    return gd_lvl, user_id, uname, ts


def _parse_guard_level_info(medal_info: dict, medal_name: Union[str, int], prefix=''):
    match medal_info.get('guard_level', 0):
        case 0:
            return False, prefix + f'啥也木有'
        case 1:
            return True, prefix + f'我的天啊，是{medal_name}最敬爱的总督大人'
        case 2:
            return True, prefix + f'我超！{medal_name}提督！'
        case 3:
            return True, prefix + f'是{medal_name}舰长呢'


class DynamicNotificationData:
    def __init__(self, name: str, dynamic_content: List[MessageSegment]):
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
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  # noqa
            'Accept-Charset': 'UTF-8,*;q=0.5',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'en-US,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43',
            # noqa
            'Referer': 'https://www.bilibili.com/'
        }
        self.cookies = None
        self.live_database = connect(f'{getcwd()}/data/db/live_notification_data.db')
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
                group_to_notify text,
                fetch_gift_price boolean
            );
            """
        )
        self.live_database.execute(
            """
            create table if not exists room_to_medal_name_table (
                room_uid varchar(200) not null unique on conflict ignore,
                medal_name varchar(200) not null 
            );
            """
        )
        self.live_database.execute(
            """
            create table if not exists bilibili_danmaku_data (
                uid text not null unique on conflict ignore,
                data_dump text
            )
            """
        )
        self.live_database.execute(
            """
            create table if not exists sail_data_check(
                uid varchar(200) not null unique on conflict ignore,
                guard_level integer not null default 0,
                room_id varchar(200) not null,
                username varchar(200) not null,
                expiry_time varchar(200) not null
            )
            """
        )

        self.live_database.execute(
            """create index if not exists idx_live_notification_bilibili_uid
            on live_notification_bilibili(uid)"""
        )
        self.live_database.execute(
            """create index if not exists idx_room_to_medal_name_table_medal_name
            on room_to_medal_name_table(medal_name)"""
        )
        self.live_database.execute(
            """create index if not exists idx_sail_data_check_uid_room_id
            on sail_data_check(uid, room_id)"""
        )

        self.live_database.commit()

    @staticmethod
    def _ensure_group_id_list(raw: Union[str, list, None]) -> List[str]:
        if raw is None:
            return []

        if isinstance(raw, list):
            return [str(x) for x in raw]

        if isinstance(raw, str):
            if not raw.strip():
                return []
            try:
                decoded = loads(raw)
            except Exception as err:
                logger.error(f'Failed to decode group id list from db: {err.__class__}')
                return []
            if isinstance(decoded, list):
                return [str(x) for x in decoded]
            return []

        return []

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
            group_to_notify = data[5]
            logger.info(f'Data found: uid: {uid}, groups: {group_to_notify}')

            await self.update_streamer_data(streamer_name, uid, group_to_notify, False)

    async def _check_if_notification_exist_in_db(self, streamer_name) -> bool:
        data = await self._get_one_notification_data_from_db(streamer_name)
        return data is not None

    def get_room_uid_from_medal_name(self, medal_name: str) -> str:
        data = self.live_database.execute(
            """
                select room_uid from room_to_medal_name_table where medal_name = ?
                """, (medal_name.strip(),)).fetchone()

        return data if not isinstance(data, tuple) else data[0]

    def get_medal_name_from_room_uid(self, room_id: str) -> str:
        data = self.live_database.execute(
            """
        select medal_name from room_to_medal_name_table where room_uid = ?
        """, (room_id,)).fetchone()

        return data if not isinstance(data, tuple) else data[0]

    def insert_sail_data(
            self, uid: Union[int, str], guard_level: int,
            room_id: Union[int, str], username: str, expiry_date=None):
        self.live_database.execute(
            """
            insert or replace into sail_data_check(uid, guard_level, room_id, username, expiry_time) 
            values (?, ?, ?, ?, ?)
            """, (
                str(uid), guard_level, str(room_id), username,
                str(time() + 60 * 60 * 24 * 31) if not expiry_date else expiry_date)
        )
        self.live_database.commit()

    def retrieve_sail_data(self, uid: Union[int, str], room_id: Union[int, str]):
        data = self.live_database.execute("""
        select guard_level, username, expiry_time from sail_data_check where uid = ? and room_id = ?
        """, (str(uid), str(room_id))).fetchone()

        if data is None:
            return None

        return data

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
        group_ids_raw = self.get_group_ids_for_streamer(name)
        group_ids = self._ensure_group_id_list(group_ids_raw)

        group_ids.append(str(group_id))
        group_ids = dumps(list(set(group_ids)))
        self.live_database.execute(
            """
            update live_notification_bilibili set uid = ?, group_to_notify = ?, isEnabled = ? where name = ?
            """, (uid, group_ids, is_enabled, name)
        )
        self.live_database.commit()

    async def add_data_to_bilibili_notify_database(self, name: str, uid: str, group_id: str):
        streamer_groups_raw = self.get_group_ids_for_streamer(name)

        if await self._check_if_notification_exist_in_db(name):
            await self.update_streamer_data(name, uid, group_id)
            return

        streamer_group_list = self._ensure_group_id_list(streamer_groups_raw)
        streamer_group_list.append(str(group_id))
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
    async def convert_live_data_to_string(data: LiveNotificationData) -> List[MessageSegment]:
        response = [MessageSegment.text(f'{data.streamer_name}{data.live_change_status}\n')]
        if data.is_live:
            response += MessageSegment.text(
                f'直播标题：{data.stream_title}\n'
                f'开播时间：{data.stream_live_time}\n')
            if data.stream_thumbnail:
                response += MessageSegment.image(data.stream_thumbnail)
            response += MessageSegment.text(f'直播标签：{data.tags}')

        return response

    def dump_live_data(self, data: str):
        uid = str(uuid1())
        self.live_database.execute(
            """
            insert into bilibili_danmaku_data (uid, data_dump) values (?, ?)
            """, (uid, data)
        )
        self.live_database.commit()

    def get_dumped_live_data(self):
        data = self.live_database.execute(
            """
            select * from bilibili_danmaku_data
            """
        ).fetchall()

        return self._analyze_dumped_live_data(data)

    @staticmethod
    def stringify_danmaku_data(data: LivestreamDanmakuData) -> Message:
        word_cloud = WordCloud(font_path=f'{getcwd()}/Services/util/SourceHanSansSC-Bold.otf',
                               background_color='#fff',
                               max_words=90,
                               width=1920,
                               height=1080).generate_from_frequencies(data.danmaku_frequency_dict)
        word_cloud_file_path = f'{getcwd()}/data/pixivPic/{int(time_ns())}.png'
        word_cloud.to_file(word_cloud_file_path)

        new_captains_prompt = f'新舰长{data.new_captains}个\n' if data.new_captains >= 3 else ''
        gift_price_string = f'（预估收入：￥{data.gift_total_price:.2f}）\n' if data.gift_total_price > 0 else ''
        danmaku_graph_data = MessageSegment.image(data.danmaku_analyze_graph) if data.danmaku_analyze_graph else ''

        return construct_message_chain(
            '直播已结束！撒花~✿✿ヽ(°▽°)ノ✿\n',
            f'一共收到啦{data.danmaku_count}枚弹幕\n',
            new_captains_prompt,
            f'收到礼物（包括SC）{data.gift_received_count}个\n',
            f'{gift_price_string}',
            f'最高人气排名：{data.highest_rank}\n',
            # f'{hotspot_data_prompt}\n\n',
            MessageSegment.image(word_cloud_file_path),
            danmaku_graph_data)

    def _delete_dumped_live_data(self, uid):
        self.live_database.execute(
            """
            delete from bilibili_danmaku_data where uid = ?
            """, (uid,)
        )
        self.live_database.commit()

    def _analyze_dumped_live_data(self, datas) -> List[LivestreamDanmakuData]:
        unpickled_data_list = []
        uids_to_delete: List[str] = []

        for data in datas:
            uid = data[0]
            dumped_data: str = data[1]
            unpickled_data: LivestreamDanmakuData = pickle.loads(codecs.decode(dumped_data.encode(), "base64"))
            unpickled_data_list.append(unpickled_data)
            uids_to_delete.append(uid)

        if uids_to_delete:
            self.live_database.executemany(
                """delete from bilibili_danmaku_data where uid = ?""",
                [(uid,) for uid in uids_to_delete],
            )
            self.live_database.commit()

        return unpickled_data_list

    def check_if_live_cached(self, room_id: str) -> bool:
        user_needs_to_be_checked = self.live_database.execute(
            """
            select last_record_live_status from live_notification_bilibili where uid = ?
            """, (room_id,)
        ).fetchone()

        is_live = user_needs_to_be_checked is not None and user_needs_to_be_checked[0]
        logger.success(f'Live cache hit, result returned: {is_live}')

        return is_live

    def is_fetch_gift_price(self, room_id: str) -> bool:
        user_needs_to_be_checked = self.live_database.execute(
            """
            select fetch_gift_price from live_notification_bilibili where uid = ?
            """, (room_id,)
        ).fetchone()

        fetch_gift_price = user_needs_to_be_checked is not None and user_needs_to_be_checked[0]
        logger.success(f'If fetch gift price?: {fetch_gift_price}')

        return fetch_gift_price

    async def check_if_live(self, room_id: str, streamer_name: str) -> LiveNotificationData:
        logger.info(f'Checking live stat for {streamer_name}, room id: {room_id}')
        url = self.bilibili_live_check_url + room_id
        data_response_client = await global_httpx_client.get(url, headers={
            'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/84.0.4147.125 Safari/537.36'
        })
        data_response_json = data_response_client.json()
        is_live = OptionalDict(data_response_json).map('data') \
            .map('live_status') \
            .or_else(0)

        if is_live != 1:
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
            .or_else('')
        if thumbnail_url:
            stream_thumbnail_filename = (
                path.join(BILIBILI_PIC_PATH, thumbnail_url.split("/")[-1].replace("]", "")
                          .replace("[", ""))).__str__()
            stream_thumbnail_filename = await global_httpx_client.download(thumbnail_url,
                                                                           file_name=stream_thumbnail_filename)
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
            select name, isEnabled, uid, last_record_live_status, group_to_notify from live_notification_bilibili
            """
        ).fetchall()

        live_data_list = []

        for live_data in user_needs_to_be_checked:
            streamer_name, is_enabled, room_id, last_record_state, group_ids = live_data

            if not is_enabled:
                logger.info(f'{streamer_name} is disable to send notification.')
                continue

            try:
                notify_data = await self.check_if_live(room_id, streamer_name)
            except Exception as err:
                logger.error(f'Failed to get live information for {streamer_name} :: {err.__class__}')
                continue

            if last_record_state != notify_data.is_live:
                if notify_data.is_live:
                    notify_data.set_live_change_status('开播啦！')
                    live_data_list.append(notify_data)
                    _start_danmaku_process_in_new_terminal(room_id, group_ids, notify_data.stream_live_time)
                else:
                    notify_data = LiveNotificationData(streamer_name, False)
                    notify_data.set_live_change_status('下播啦！')
                    live_data_list.append(notify_data)

                await self.update_live_status(streamer_name, notify_data.is_live)

        return live_data_list


def create_new_cookie(r1):
    return f'innersign=0; buvid3={r1["data"]["b_3"]}; b_nut=1704873471;' \
           f' i-wanna-go-back=-1; b_ut=7; b_lsid=9910433CB_18CF260AB89;' \
           f' _uuid=312C2F31-1D48-E108C-4232-D7E96B104A8D1070864infoc; enable_web_push=DISABLE; ' \
           f'header_theme_version=undefined; home_feed_column=4; browser_resolution=839-959;' \
           f' buvid4={r1["data"]["b_4"]}; buvid_fp=946265982c5f2c530cfed6f97df5cf65'


class BilibiliOnSail(LiveNotification):
    def __init__(self):
        super().__init__()
        self.sail_verification_url = f'https://api.live.bilibili.com/xlive/web-ucenter/user/MedalWall?target_id='

    @alru_cache(ttl=60 * 10)
    async def check_if_uid_has_guard(self, uid: str, medal_name: str) -> (bool, str):
        if not uid.isdigit():
            return False, '查询UID必须是数字。用法：！查上海 用户UID 牌子名称'

        if not uid or not medal_name:
            return False, 'UID和/或牌子名不能为空字符'

        prefix = ''
        text = '啥也木有'
        medal_name = medal_name.strip()
        if medal_name.isdigit():
            success, text = await self._retrieve_sail_from_cache(medal_name, prefix, uid)
            if success:
                return success, text

            medal_name = self.get_medal_name_from_room_uid(medal_name)
        else:
            room_uid = self.get_room_uid_from_medal_name(medal_name)
            if room_uid:
                success, result = await self._retrieve_sail_from_cache(room_uid, prefix, uid)
                if success:
                    return success, result

                logger.info('Failed to find sail data from cache. Falling back...')

        if not self.cookies:
            self.cookies, self.headers = await update_buvid_params()
        async with ClientSession() as client:
            async with client.get(
                    self.sail_verification_url + uid + f'&_={int(time())}',
                    headers=self.headers, cookies=self.cookies) as resp:
                data_json = await resp.json()

        code = OptionalDict(data_json).map("code").or_else("?")
        logger.info(f'Live sail data for {uid} for {medal_name}: {OptionalDict(data_json).map("code").or_else("?")}')

        if code != 0:
            self.cookies, self.headers = await update_buvid_params()
            return False, '喜报：数据错误，someone tells 祈雨，灵夜坏了。请重试一次看看~'

        username = OptionalDict(data_json).map('data').map('name').or_else('?')
        if OptionalDict(data_json).map('data').map('only_show_wearing').or_else(1) != 0:
            prefix = f'由于用户隐私设置，可能无法查询其牌子/上舰情况。\n\n'

        prefix += f'用户 {username} '
        medal_lists = OptionalDict(data_json).map('data').map('list').or_else([])
        for data in medal_lists:
            medal_info = data.get('medal_info', {})
            medal_name_inner = medal_info.get('medal_name', '').strip()

            logger.info(f'Medal info data: {medal_info}')
            if medal_name_inner == medal_name:
                return _parse_guard_level_info(medal_info, medal_name, prefix)

        return False, text

    def backfill_sail_data(self):
        with open(f'{getcwd()}/0111.txt', "r", encoding="utf-8") as infile:
            for line in infile:
                if not line.strip():
                    continue

                gd_lvl, user_id, uname, ts = _parse_line(line)
                logger.info(f'Inserting {gd_lvl} {user_id} {uname} {ts}')
                self.insert_sail_data(user_id, gd_lvl, 1852504554, uname, ts)

    async def _retrieve_sail_from_cache(self, room_id, prefix, uid):
        if (cached_data := self.retrieve_sail_data(uid, room_id)) is None:
            return False, prefix + '啥也木有'
        logger.debug(f'Sail data: {cached_data}')
        guard_level, username, expiry_time = cached_data
        if float(expiry_time) < time():
            return False, '以前有牌子但是过期了的老舰长'
        medal_name_str = self.get_medal_name_from_room_uid(room_id)
        if medal_name_str:
            room_id = medal_name_str
        return _parse_guard_level_info({'guard_level': guard_level}, room_id, f'用户 {username} ')


class BilibiliDynamicNotifcation(LiveNotification):
    def __init__(self):
        super().__init__()
        self.dynamic_url = f'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid='
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
                last_dynamic_id var(200) not null,
                dynamic_time var(100) not null,
                group_to_notify text not null
            )
            """
        )

        self.live_database.execute(
            """create index if not exists idx_dynamic_notification_bilibili_name
            on dynamic_notification_bilibili(name)"""
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
        else:
            self.live_database.execute(
                """
                update dynamic_notification_bilibili set group_to_notify = ?, isEnabled = 1 where name = ?
                """, (dumps(group_ids), name)
            )

        self.live_database.commit()

    async def get_group_to_notify(self, name) -> Union[List[str], None]:
        data = self.live_database.execute(
            """
            select group_to_notify from dynamic_notification_bilibili where name = ?
            """, (name,)
        ).fetchone()

        if data is None:
            return None

        return self._ensure_group_id_list(data[0])

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

        if user_needs_to_be_checked is not None:
            user_name = user_needs_to_be_checked[0]
            is_enabled = user_needs_to_be_checked[1]
            if not is_enabled:
                return None

            mid = user_needs_to_be_checked[2]
            last_dynamic_id = user_needs_to_be_checked[3]
            last_check_dynamic_time = int(user_needs_to_be_checked[4])

            if not self.cookies:
                self.cookies, self.headers = await update_buvid_params()
            async with ClientSession() as client:
                async with client.get(
                        self.dynamic_url + mid + f'&_={int(time())}',
                        headers=self.headers, cookies=self.cookies) as resp:
                    dynamic_json = await resp.json()

            code = OptionalDict(dynamic_json).map("code").or_else("?")
            logger.info(f'Dynamic json for {name}: {OptionalDict(dynamic_json).map("code").or_else("?")}')

            if code != 0:
                self.cookies, self.headers = await update_buvid_params()
            for item in OptionalDict(dynamic_json).map('data').map('items').or_else([]):
                modules = OptionalDict(item).map('modules').or_else({})
                module_tag = OptionalDict(modules).map('module_tag').map('text').or_else('')
                if module_tag == '置顶':
                    continue

                dynamic_id = OptionalDict(item).map('id_str').or_else('')
                dynamic_time = int(OptionalDict(modules).map('module_author').map('pub_ts').or_else(0))
                dynamic_type = OptionalDict(item).map('type').or_else('')
                if dynamic_type == self.LIVESTREAM_DYNAMIC_TYPE:
                    continue

                # Reverted to one of the past dynamic for some reason
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

    async def _analyze_dynamic(self, item: dict) -> List[MessageSegment]:
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
            orig_text += await self._fetch_draw_from_dynamic(orig_data_draw)
        if orig_data:
            orig_text += MessageSegment.text('\n其他内容：\n') + await self._fetch_content_in_orig_node(orig_data)

        return orig_text

    @staticmethod
    async def construct_string_from_data(data: DynamicNotificationData) -> Message:
        return construct_message_chain(f'{data.name}发新动态啦~\n\n', data.dynamic_content)

    @staticmethod
    async def _fetch_draw_from_dynamic(orig_draw_node) -> List[MessageSegment]:
        draw_id = OptionalDict(orig_draw_node).map('id').or_else('')
        if not draw_id:
            return [MessageSegment.text('')]

        orig_text: List[MessageSegment] = []
        for idx, item in enumerate(OptionalDict(orig_draw_node).map('items').or_else([])):
            file_name = path.join(BILIBILI_PIC_PATH, f'{draw_id}_{idx}')
            file_name = await global_httpx_client.download(item['src'], file_name)
            orig_text.append(MessageSegment.image(file_name))

        return orig_text

    async def _fetch_content_in_text_node(self, rich_text_node) -> List[MessageSegment]:
        orig_text: List[MessageSegment] = []
        for text_node in rich_text_node:
            node_type = OptionalDict(text_node).map('type').or_else('')
            if node_type != self.EMOJI_DYNAMIC_TYPE:
                orig_text.append(MessageSegment.text(OptionalDict(text_node).map('orig_text').or_else('')))
            if node_type == self.AT_DYNAMIC_TYPE:
                at_text = OptionalDict(text_node).map('orig_text').or_else('')
                orig_text.append(
                    MessageSegment.text(
                        '@' if '@' not in at_text else '' + OptionalDict(text_node).map(
                            'orig_text').or_else('') + ' '))
            elif node_type == self.EMOJI_DYNAMIC_TYPE:
                file_name = (f"{getcwd()}/data/bilibiliPic/"
                             f"{OptionalDict(text_node).map('emoji').map('text').or_else(str(time()))}.jpg"
                             .replace('[', '').replace(']', ''))
                file_url = OptionalDict(text_node).map('emoji').map('icon_url').or_else('')
                if file_url:
                    file_url = await global_httpx_client.download(file_url, file_name)
                orig_text.append(MessageSegment.image(file_url))
                orig_text.append(MessageSegment.text('\n'))

        return orig_text

    async def _fetch_content_in_orig_node(self, major_dynamic: dict) -> List[MessageSegment]:
        rich_text_node = OptionalDict(major_dynamic) \
            .map('desc') \
            .map('rich_text_nodes') \
            .or_else([])
        orig_text = await self._fetch_content_in_text_node(rich_text_node)

        pic = OptionalDict(major_dynamic).map('major').map('draw').or_else({})
        archive = OptionalDict(major_dynamic).map('major').map('archive').or_else({})
        opus = OptionalDict(major_dynamic).map('major').map('opus').or_else({})

        if opus:
            summaries = OptionalDict(opus).map('summary').map('text').or_else('')
            orig_text.append(MessageSegment.text(summaries))
            files = OptionalDict(opus).map('pics').or_else([])
            for idx, file in enumerate(files):
                file_url: str = file['url']
                file_name = file_url.split('/')[-1]
                file_name = await global_httpx_client.download(file['url'], path.join(BILIBILI_PIC_PATH, file_name))
                orig_text.append(MessageSegment.image(file_name))

        if pic:
            pic_id = pic['id']
            files = pic['items']
            for idx, file in enumerate(files):
                file_name = f"{getcwd()}/data/bilibiliPic/{pic_id}_{idx}.jpg"
                file_name = await global_httpx_client.download(file['src'], file_name)
                orig_text.append(MessageSegment.image(file_name))

        if archive:
            bvid = archive['bvid']
            forwarded_video_cover = f"{getcwd()}/data/bilibiliPic/{bvid}.jpg"

            forwarded_video_cover = await global_httpx_client.download(archive['cover'], forwarded_video_cover)

            orig_text.append(MessageSegment.text(
                f'\n转发视频标题：{archive["title"]}\n'
                f'转发视频：https://www.bilibili.com/video/{bvid}\n'))
            orig_text.append(MessageSegment.image(forwarded_video_cover))

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
    async def _analyze_video_dynamic_content(archive_object) -> List[MessageSegment]:
        if not archive_object:
            return []

        video_cover = OptionalDict(archive_object).map('cover').or_else('')
        bvid = OptionalDict(archive_object).map('bvid').or_else(str(time()))
        file_name = f"{getcwd()}/data/bilibiliPic/{bvid}.jpg"
        if video_cover:
            file_name = await global_httpx_client.download(video_cover, file_name)

        return [MessageSegment.text('发布了新视频：\n'
                                    f'标题：{OptionalDict(archive_object).map("title").or_else("未知")}\n'
                                    f'蓝链：https://www.bilibili.com/video/{bvid}\n'),
                MessageSegment.image(file_name)]


def _start_danmaku_process_in_new_terminal(room_id: str, group_ids: str, stream_live_time: str):
    danmaku_cmd = f'{DANMAKU_PROCESS} {room_id} {group_ids} "{stream_live_time}"'

    if os.name == 'nt':
        try:
            return Popen(['wt', 'new-tab', '--', 'cmd', '/k', danmaku_cmd])
        except OSError as err:
            logger.error(f'Failed to start danmaku process in Windows Terminal, falling back to cmd start: {err}')

        try:
            return Popen(['cmd', '/c', 'start', 'Danmaku', 'cmd', '/k', danmaku_cmd])
        except OSError as err:
            logger.error(f'Failed to start danmaku process via cmd start as well: {err}')
            return None

    terminal_emulators = [
        ('x-terminal-emulator', ['x-terminal-emulator', '-e']),
        ('gnome-terminal', ['gnome-terminal', '--']),
        ('konsole', ['konsole', '-e']),
        ('xfce4-terminal', ['xfce4-terminal', '-e']),
        ('mate-terminal', ['mate-terminal', '-e']),
        ('lxterminal', ['lxterminal', '-e']),
        ('xterm', ['xterm', '-e']),
    ]

    for exe, base_argv in terminal_emulators:
        if shutil.which(exe):
            try:
                return Popen(base_argv + ['sh', '-lc', danmaku_cmd])
            except OSError as err:
                logger.error(f'Failed to start danmaku in terminal {exe}: {err}')

    try:
        if os.name == 'posix':
            return Popen(
                ['sh', '-lc', danmaku_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return Popen(['sh', '-lc', danmaku_cmd])
    except OSError as err:
        logger.error(f'Failed to start danmaku process on unix fallback: {err}')
        return None
