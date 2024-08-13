# -*- coding: utf-8 -*-
# !/usr/bin/env python3.10
import asyncio
import codecs
import http.cookies
import pickle
import re
import sys
import time
from functools import lru_cache
from os import getpid
from typing import Optional, Set, List, Dict

import aiohttp
from nonebot.log import logger

import blivedm.models.web as web_models
from Services.live_notification import LiveNotification, LivestreamDanmakuData
from Services.util.common_util import OptionalDict, find_repeated_substring, construct_timestamp_string
from blivedm import BaseHandler, BLiveClient
from blivedm.clients import ws_base
from config import BILI_SESS_DATA

FIVE_MINUTES = 60 * 5
TWENTY_FIVE_MINUTES = 60 * 25
TOP_TIMESTAMP_LIMIT = 7


def _get_log_filename() -> str:
    return f'log_{int(time.time())}_{getpid()}.log'


live_notification = LiveNotification()
logger.add(f'./logs/{_get_log_filename()}', level='INFO', colorize=False, backtrace=True, diagnose=True,
           rotation='50MB', retention='3 days')


class MyDanmakuHandler(BaseHandler):
    def __init__(self):
        self.danmaku_frequency_dict = {}
        # TODO: make this store in a file or a db.
        self.blacklist_word: Set[str] = {'老板大气', 'B站无互动', '请移步T台', '中奖喷雾', '点点红包', '转人工'}

        self.highest_rank = 99999
        self.like_received_count = self.danmaku_count = 0
        self.gift_received_count = self.new_captains = self.gift_price = 0
        self.room_id = self.group_ids = ''

        self.stream_start_time = time.time()
        self.stream_hotspot_timestamp_list: List[float] = []

    def set_room_id(self, parsed_in_room_id: str):
        self.room_id = parsed_in_room_id

    def set_group_ids(self, group_ids_dumped: str):
        self.group_ids = group_ids_dumped

    def add_danmaku_into_frequency_dict(self, message):
        msg = message.msg.lower()
        msg = msg.replace('（', '').replace('）', '').replace('(', '').replace(')', '')

        if self._is_blacklist_word(msg):
            return

        self.danmaku_count += 1
        logger.info(f'Message received: {message.msg}, name: {message.uname}, receive_time: {message.timestamp}')

        time_elapsed_time = time.time() - self.stream_start_time
        if time_elapsed_time > FIVE_MINUTES:
            self.stream_hotspot_timestamp_list.append(time_elapsed_time)

        if not re.fullmatch(r'[\s+,，。、?？！!]+', msg):
            message_list = list(set(re.split(r'[\s+,，。、?？！!]', msg)))
        else:
            message_list = [msg]
        for message in message_list:
            message = find_repeated_substring(message.strip())
            if message and len(message) <= 9:
                if message not in self.danmaku_frequency_dict:
                    self.danmaku_frequency_dict[message] = 1
                else:
                    self.danmaku_frequency_dict[message] += 1

    _CMD_CALLBACK_DICT = BaseHandler._CMD_CALLBACK_DICT.copy()

    @lru_cache(maxsize=800)
    def _is_blacklist_word(self, message: str) -> bool:
        for blacklist in self.blacklist_word:
            if blacklist in message:
                return True

        return False

    def _like_info_v3_callback(self, client: BLiveClient, command: dict):
        self.like_received_count += 1
        logger.info(f'收到点赞， {client.room_id}, 点赞人：{OptionalDict(command).map("data").map("uname").or_else("?")}')

    # noinspection PyUnusedLocal
    def _popularity_change(self, client: BLiveClient, command: dict):
        logger.info(f'Command: {command}')

        rank = OptionalDict(command).map("data").map("rank").or_else(999)
        logger.info(f'人气榜变动，目前人气档位：{rank}')
        if rank > 0:
            self.highest_rank = min(self.highest_rank, rank)

    # noinspection PyUnusedLocal
    def _user_toast_msg(self, client: BLiveClient, command: dict):
        captain_price = 0
        captain_count = 0

        if command['cmd'] == 'USER_TOAST_MSG_V2':
            if OptionalDict(command).map("guard_info").or_else(None) is not None:
                captain_data = OptionalDict(command).map("data").map("pay_info").or_else({})
                captain_price = OptionalDict(captain_data).map("price").or_else(0)
                captain_count = OptionalDict(captain_data).map("num").or_else(0)
        else:
            if OptionalDict(command).map("data").or_else(None) is not None:
                captain_price = OptionalDict(command).map("data").map("price").or_else(0)
                captain_count = OptionalDict(command).map("data").map("num").or_else(0)
                logger.info(f'有新舰长？：{OptionalDict(command).map("guard_info").map("role_name").or_else("未知数据")}'
                            f' x {captain_count} -> 价格：{captain_price}')
        if captain_price > 0:
            self.gift_price += (captain_price / 1000) * captain_count

        self.new_captains += captain_count

    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['LIKE_INFO_V3_CLICK'] = _like_info_v3_callback
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['POPULAR_RANK_CHANGED'] = _popularity_change
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['USER_TOAST_MSG'] = _user_toast_msg
    # noinspection PyTypeChecker
    _CMD_CALLBACK_DICT['USER_TOAST_MSG_V2'] = _user_toast_msg

    def _on_heartbeat(self, client: ws_base.WebSocketClientBase, message: web_models.HeartbeatMessage):
        if not live_notification.check_if_live_cached(self.room_id):
            logger.success(f'Livestream is not going anymore for room id: {self.room_id},'
                           f' dumping the data. Total gift value: {self.gift_price}')

            try:
                hotspot_timestamp_data = get_sorted_timestamp_hotspot(
                    self.stream_hotspot_timestamp_list, TWENTY_FIVE_MINUTES)
            except Exception as err:
                logger.error(f'Failed to get hotspot data: {err.__class__}')
                hotspot_timestamp_data = []

            pickled_data = codecs.encode(pickle.dumps(LivestreamDanmakuData(
                danmaku_count=self.danmaku_count,
                danmaku_frequency_dict=self.danmaku_frequency_dict,
                qq_group_dumped=self.group_ids,
                like_received_count=self.like_received_count,
                gift_received_count=self.gift_received_count,
                highest_rank=self.highest_rank if self.highest_rank <= 100 else '未知',
                gift_total_price=self.gift_price if live_notification.is_fetch_gift_price(self.room_id) else 0,
                new_captains=self.new_captains,
                top_crazy_timestamps=hotspot_timestamp_data,
            )), 'base64').decode()
            live_notification.dump_live_data(pickled_data)

            find_repeated_substring.cache_clear()
            exit(1)

    def _on_gift(self, client: BLiveClient, message: web_models.GiftMessage):
        self.gift_received_count += message.num
        if message.coin_type.lower() == 'gold':
            self.gift_price += message.total_coin / 1000
        # logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
        #             f' （{message.coin_type}瓜子x{message.total_coin}）')

    def _on_danmaku(self, client: BLiveClient, message: web_models.DanmakuMessage):
        self.add_danmaku_into_frequency_dict(message)

    def _on_super_chat(self, client: BLiveClient, message: web_models.SuperChatMessage):
        self.gift_received_count += 1
        self.gift_price += message.price
        logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')


# 直播间ID的取值看直播间URL
TEST_ROOM_IDS = []

# 这里填一个已登录账号的cookie。不填cookie也可以连接，但是收到弹幕的用户名会打码，UID会变成0
SESSDATA = BILI_SESS_DATA

session: Optional[aiohttp.ClientSession] = None
handler = MyDanmakuHandler()


async def main():
    global TEST_ROOM_IDS
    argv = sys.argv
    if not sys.argv or len(argv) != 3:
        raise RuntimeError('No argv, should includes at least one room id.')
    else:
        room_id = argv[1]
        group_ids = argv[2]
        handler.set_room_id(room_id)
        handler.set_group_ids(group_ids)
        TEST_ROOM_IDS.append(room_id)
    init_session()
    try:
        await run_listening()
    finally:
        await session.close()


def init_session():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)


def hotspot_analyzation(timestamps: List[float], intervals=60) -> Dict[float, float]:
    """Analyzing frequency for a given list of danmaku in a certain interval"""
    timestamps.sort()
    result_dict = {}

    for timestamp in timestamps:
        interval_key = float(timestamp // intervals) * intervals
        if interval_key not in result_dict:
            result_dict[interval_key] = 1
        else:
            result_dict[interval_key] += 1

    return result_dict


def get_sorted_timestamp_hotspot(stream_time_frequency_list: List[float], intervals=60) -> List[str]:
    hotspot_analyzation_result = hotspot_analyzation(stream_time_frequency_list, intervals)
    sorted_result = sorted(hotspot_analyzation_result.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_result) > TOP_TIMESTAMP_LIMIT:
        sorted_result = sorted_result[:TOP_TIMESTAMP_LIMIT]

    hotspot_timestamp_data = [x[0] for x in sorted_result]
    return [construct_timestamp_string(x) for x in hotspot_timestamp_data]


async def run_listening():
    """
    演示同时监听多个直播间
    """
    clients = [BLiveClient(int(single_room_id), session=session) for single_room_id in TEST_ROOM_IDS]
    for client in clients:
        client.set_handler(handler)
        client.start()

    try:
        await asyncio.gather(*(
            client.join() for client in clients
        ))
    finally:
        await asyncio.gather(*(
            client.stop_and_close() for client in clients
        ))


if __name__ == '__main__':
    try:
        logger.success('Successfully started danmaku monitoring.')
        asyncio.run(main())
    finally:
        print()
