# -*- coding: utf-8 -*-
# !/usr/bin/env python3.10
import asyncio
import codecs
import http.cookies
import pickle
import re
import sys
from typing import Optional

import aiohttp
from loguru import logger

import blivedm.models.web as web_models
from Services.live_notification import LiveNotification, LivestreamDanmakuData
from Services.util.common_util import OptionalDict
from blivedm import BaseHandler, BLiveClient
from blivedm.clients import ws_base

live_notification = LiveNotification()


class MyDanmakuHandler(BaseHandler):
    def __init__(self):
        self.danmaku_frequency_dict = {}
        self.danmaku_count = 0
        self.highest_rank = 99999
        self.rank_area = ''
        self.like_received_count = 0
        self.gift_received_count = 0
        self.gift_price = 0
        self.room_id = ''
        self.group_ids = ''

    def set_room_id(self, parsed_in_room_id: str):
        self.room_id = parsed_in_room_id

    def set_group_ids(self, group_ids_dumped: str):
        self.group_ids = group_ids_dumped

    def add_danmaku_into_frequency_dict(self, msg):
        self.danmaku_count += 1
        msg = msg.replace('（', '').replace('）', '').replace('(', '').replace(')', '')
        if not re.fullmatch(r'[\s+,，。、?？！!]+', msg):
            message_list = re.split(r'[\s+,，。、?？！!]', msg)
        else:
            message_list = [msg]
        for message in message_list:
            message = message.strip()
            if len(message) <= 5 and message:
                logger.success(f'{message} is noted.')
                if message not in self.danmaku_frequency_dict:
                    self.danmaku_frequency_dict[message] = 1
                else:
                    self.danmaku_frequency_dict[message] += 1

    _CMD_CALLBACK_DICT = BaseHandler._CMD_CALLBACK_DICT.copy()

    def _like_info_v3_callback(self, client: BLiveClient, command: dict):
        self.like_received_count += 1
        logger.info(f'收到点赞， {client.room_id}, 点赞人：{OptionalDict(command).map("data").map("uname").or_else("?")}')

    def _popularity_change(self, client: BLiveClient, command: dict):
        rank = OptionalDict(command).map("data").map("rank").or_else(999)
        logger.info(f'人气榜变动，目前人气档位：{rank}')
        if rank > 0:
            self.highest_rank = min(self.highest_rank, rank)

    _CMD_CALLBACK_DICT['LIKE_INFO_V3_CLICK'] = _like_info_v3_callback
    _CMD_CALLBACK_DICT['POPULAR_RANK_CHANGED'] = _popularity_change

    def _on_heartbeat(self, client: ws_base.WebSocketClientBase, message: web_models.HeartbeatMessage):
        if not live_notification.check_if_live_cached(self.room_id):
            logger.success(f'Livestream is not going anymore for room id: {self.room_id},'
                           f' dumping the data. Total gift value: {self.gift_price}')
            pickled_data = codecs.encode(pickle.dumps(LivestreamDanmakuData(
                danmaku_count=self.danmaku_count,
                danmaku_frequency_dict=self.danmaku_frequency_dict,
                qq_group_dumped=self.group_ids,
                like_received_count=self.like_received_count,
                gift_received_count=self.gift_received_count,
                highest_rank=self.highest_rank if self.highest_rank <= 100 else '未知',
                gift_total_price=self.gift_price if live_notification.is_fetch_gift_price(self.room_id) else 0
            )), 'base64').decode()
            live_notification.dump_live_data(pickled_data)
            exit(1)

    def _on_gift(self, client: BLiveClient, message: web_models.GiftMessage):
        self.gift_received_count += message.num
        if message.coin_type.lower() == 'gold':
            self.gift_price += message.total_coin / 1000

        logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
                    f' （{message.coin_type}瓜子x{message.total_coin}）')

    def _on_danmaku(self, client: BLiveClient, message: web_models.DanmakuMessage):
        logger.info(f'Message received: {message.msg}, name: {message.uname}, receive_time: {message.timestamp}')
        self.add_danmaku_into_frequency_dict(message.msg)

    def _on_super_chat(self, client: BLiveClient, message: web_models.SuperChatMessage):
        self.gift_received_count += 1
        self.gift_price += message.price
        logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')


# 直播间ID的取值看直播间URL
TEST_ROOM_IDS = []

# 这里填一个已登录账号的cookie。不填cookie也可以连接，但是收到弹幕的用户名会打码，UID会变成0
SESSDATA = ''

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
        asyncio.run(main())
    finally:
        print(handler.danmaku_frequency_dict)
