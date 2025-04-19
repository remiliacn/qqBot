import dataclasses
import re
import sqlite3
from asyncio import create_subprocess_shell, sleep
from asyncio.subprocess import PIPE
from json import loads, JSONDecodeError, dumps
from os import getcwd, walk, path, listdir, mkdir
from os.path import exists
from re import findall
from shutil import move
from time import time
from typing import Union, List

from loguru import logger
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.internal.matcher import Matcher
from twitchdl import twitch
from youtube_dl.utils import sanitize_filename

from Services.live_notification import LiveNotificationData
from Services.util.common_util import OptionalDict, HttpxHelperClient
from config import SUPER_USER, PATH_TO_ONEDRIVE, SHARE_LINK, CLOUD_STORAGE_SIZE_LIMIT_GB
from model.common_model import Status, ValidatedTimestampStatus, TwitchDownloadStatus
from util.helper_util import construct_message_chain


class TwitchLiveData:
    def __init__(self, streamer_name, is_live, stream_title='', stream_thumbnail='', stream_live_time=''):
        self.streamer_name = streamer_name
        self.is_live = is_live
        self.stream_title = stream_title
        self.stream_thumbnail = stream_thumbnail
        self.stream_live_time = stream_live_time
        self.live_change_status = '开播啦'

    def set_live_change_status(self, status):
        self.live_change_status = status


class TwitchService:
    def __init__(self):
        self.live_database = sqlite3.connect(f'{getcwd()}/data/db/live_notification_data.db')
        self.client = HttpxHelperClient()
        self._init_database()

    def _init_database(self):
        self.live_database.execute(
            """
create table if not exists live_notification_twitch
(
    channel_name            text unique on conflict ignore,
    isEnabled               boolean,
    last_checked_date       varchar(200),
    last_record_live_status boolean,
    last_video_vault_time   integer,
    group_to_notify         text
)
            """
        )
        self.live_database.commit()

    async def _get_one_notification_data_from_db(self, streamer_name: str):
        data = self.live_database.execute(
            """
            select * from live_notification_twitch where channel_name = ?
            """, (streamer_name,)
        ).fetchone()

        return data

    async def _get_last_twitch_archive_id(self, streamer_name: str) -> Union[int, None]:
        data = self.live_database.execute(
            """
            select last_video_vault_time from live_notification_twitch where channel_name = ?
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

            await self.update_streamer_data(streamer_name, group_to_notify, False)

    async def update_streamer_data(self, channel_name: str, group_id: str, is_enabled=True):
        group_ids = self.get_group_ids_for_streamer(channel_name)
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
            update live_notification_twitch set group_to_notify = ?, isEnabled = ? where channel_name = ?
            """, (group_ids, is_enabled, channel_name)
        )
        self.live_database.commit()

    def get_group_ids_for_streamer(self, name: str):
        data = self.live_database.execute(
            """
            select group_to_notify from live_notification_twitch where channel_name = ?
            """, (name,)
        ).fetchone()

        if data is None:
            return None

        return data if not isinstance(data, tuple) else data[0]

    async def _check_if_notification_exist_in_db(self, streamer_name) -> bool:
        data = await self._get_one_notification_data_from_db(streamer_name)
        return data is not None

    async def add_data_to_twitch_notify_database(self, name: str, group_id: str):
        streamer_groups = self.get_group_ids_for_streamer(name)

        if await self._check_if_notification_exist_in_db(name):
            await self.update_streamer_data(name, group_id)
            return

        if streamer_groups is not None:
            streamer_group_list = loads(streamer_groups)
        else:
            streamer_group_list = []

        streamer_group_list.append(group_id)
        streamer_group_list = list(set(streamer_group_list))
        self.live_database.execute(
            """
            insert or replace into live_notification_twitch
                (channel_name, isEnabled, last_checked_date, 
                    last_record_live_status, group_to_notify, last_video_vault_time)
                values (?, ?, ?, ?, ?, ?)
            """, (name, True, time(), False, dumps(streamer_group_list), 0)
        )

        self.live_database.commit()

    async def update_live_status(self, streamer_name: str, status: Union[int, bool]):
        self.live_database.execute(
            """
            update live_notification_twitch 
            set last_checked_date = ?, last_record_live_status = ? 
            where channel_name = ?
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

        return response

    async def get_twitch_if_live(self, channel_name: str) -> TwitchLiveData:
        page = await self.client.get(f'https://www.twitch.tv/{channel_name}')
        potential_json_data = findall(r'({.*?]})', page.text)
        try:
            json_data = loads(potential_json_data[0])
        except JSONDecodeError:
            return TwitchLiveData(channel_name, False)

        is_live_graph = OptionalDict(json_data).map('@graph').or_else([{}])[0]
        live_title = OptionalDict(is_live_graph).map('description').or_else('')
        thumbnail_url = OptionalDict(is_live_graph).map('thumbnailUrl').or_else([''])[-1]
        if thumbnail_url:
            stream_thumbnail_filename = \
                f'{getcwd()}/data/bilibiliPic/{thumbnail_url.split("/")[-1].replace("]", "").replace("[", "")}'
            stream_thumbnail_filename = await self.client.download(thumbnail_url, file_name=stream_thumbnail_filename)
        else:
            stream_thumbnail_filename = ''

        live_time = OptionalDict(is_live_graph).map('publication').map('startDate').or_else('?')
        is_live = OptionalDict(is_live_graph).map('publication').map('isLiveBroadcast').or_else(False)
        return TwitchLiveData(channel_name, is_live, live_title, stream_thumbnail_filename, live_time)

    async def check_live_twitch(self) -> List[LiveNotificationData]:
        user_needs_to_be_checked = self.live_database.execute(
            """
            select * from live_notification_twitch
            """
        ).fetchall()

        live_data_list = []

        for live_data in user_needs_to_be_checked:
            streamer_name = live_data[0]
            is_enabled = live_data[1]
            last_record_state = live_data[3]

            if not is_enabled:
                logger.info(f'{streamer_name} is disable to send notification.')
                continue

            notify_data = await self.get_twitch_if_live(streamer_name)
            if last_record_state != notify_data.is_live:
                if notify_data.is_live:
                    logger.success(f'{streamer_name} is live')
                    notify_data.set_live_change_status('开播啦！')
                    live_data_list.append(notify_data)
                else:
                    notify_data = LiveNotificationData(streamer_name, False)
                    logger.success(f'{streamer_name} is gone!!!!')
                    notify_data.set_live_change_status('下播啦！')
                    live_data_list.append(notify_data)

                await self.update_live_status(streamer_name, notify_data.is_live)

        return live_data_list


@dataclasses.dataclass
class TwitchClipInstruction:
    video_id: str
    start_time: str = ''
    end_time: str = ''
    file_name: str = ''


class TwitchClippingService:
    def __init__(self):
        self.TIMESTAMP_FORMAT = re.compile(r'(\d+[：:]){1,2}\d+')

        self.data_found_notification_done = False
        self.ffmpeg_notification_done = False
        self.downloaded_notification_done = False
        self.downloading_notification_done = False

    async def analyze_clip_comment(self, message_arg: str, session: Matcher) -> Status:
        message_arg = message_arg.split()
        if len(message_arg) < 1:
            return Status(False,
                          '指令错误，应该为！切片 视频id 开始时间戳 停切时间戳\n例子：！切片 2206229026 00:00:00 00:05:00')

        video_id = message_arg[0]
        await session.send('我去去就回~')
        if len(message_arg) == 1 and (video_id.isnumeric() or 'videos/' in video_id):
            return Status(True, TwitchClipInstruction(video_id))

        if not video_id.isnumeric():
            if 'videos/' not in video_id:
                try:
                    video_list = await self._get_twitch_archive_list(video_id)
                    if not video_list['videos']:
                        return Status(False, '你这是让我切谁呢？要不你给个videoID我再试试？')
                except Exception as err:
                    logger.exception(f'Failed to retrieve streamer data: {err.__class__}')
                    return Status(False, f'出问题了！{err}')

                video_id = video_list['videos'][0]['id']
                logger.info(f'Found video id: {video_id}')
            else:
                video_id = video_id.split('/')[-1]
                if not video_id.isnumeric():
                    return Status(False, '你这是让我切谁呢？ 要不给一个主播名试试？')

        start_time = ''
        end_time = ''
        file_name = ''

        if len(message_arg) == 2:
            start_time = message_arg[1].strip()
            if not self.TIMESTAMP_FORMAT.fullmatch(start_time):
                return Status(False, '起始时间戳必须是小时:分钟:秒钟的格式')
        if len(message_arg) >= 3:
            start_time = message_arg[1].strip()
            end_time = message_arg[2].strip()

            if not self.TIMESTAMP_FORMAT.fullmatch(start_time):
                return Status(False, '起始时间戳必须是小时:分钟:秒钟的格式')

            if not self.TIMESTAMP_FORMAT.fullmatch(end_time):
                return Status(False, '结束时间戳必须是小时:分钟:秒钟的格式')

            if len(message_arg) >= 4:
                file_name = f'{sanitize_filename("_".join(message_arg[3:]).strip())}.mp4'

        start_time = start_time.replace('：', ':')
        end_time = end_time.replace('：', ':')

        if not start_time and not end_time:
            return Status(True, TwitchClipInstruction(video_id))

        validate_start_time = await self._validate_timestamp(start_time)
        validate_end_time = await self._validate_timestamp(end_time)

        if not validate_end_time.is_success:
            return validate_end_time

        if not validate_start_time.is_success:
            return validate_start_time

        start_time = validate_start_time.validated_timestamp
        end_time = validate_end_time.validated_timestamp
        return Status(True, TwitchClipInstruction(video_id, start_time, end_time, file_name))

    @staticmethod
    async def _get_twitch_archive_list(channel_name: str) -> dict:
        total_count, generator = twitch.channel_videos_generator(
            channel_name, 5, 'time', 'archive', game_ids=[]
        )
        videos = list(generator)
        data = {"count": len(videos), "totalCount": total_count, "videos": videos}
        return data

    @staticmethod
    async def _validate_timestamp(timestamp: str) -> ValidatedTimestampStatus:
        splitted_data = timestamp.split(':')
        hour = '0'
        if len(splitted_data) == 2:
            minute, second = splitted_data
        else:
            hour, minute, second = splitted_data

        hour = int(hour)
        minute = int(minute)
        second = int(second)

        if hour < 0:
            return ValidatedTimestampStatus(False, '你在干嘛？')
        if minute < 0 or minute > 59:
            return ValidatedTimestampStatus(False, '你在干嘛？')
        if second < 0 or second > 59:
            return ValidatedTimestampStatus(False, '你在干嘛？')

        return ValidatedTimestampStatus(True, '', f'{hour:02}:{minute:02}:{second:02}')

    @staticmethod
    async def _check_space_used():
        size_limit_bytes = CLOUD_STORAGE_SIZE_LIMIT_GB * (1024 ** 3)
        for root, _, files in walk(f'{getcwd()}/data/twitch'):
            for file in files:
                file_path = path.join(root, file)
                try:
                    file_size = path.getsize(file_path)
                    if file_size > size_limit_bytes:
                        return Status(False, construct_message_chain(f'Someone tell ', MessageSegment.at(SUPER_USER),
                                                                     f' there is not enough space in the disk.'))
                except OSError as err:
                    return Status(False,
                                  f'Someone tell [CQ:at,qq={SUPER_USER}] '
                                  f'there is problem with downloading. {err.__class__}')

        return Status(True, None)

    async def download_twitch_videos(self, instruction: TwitchClipInstruction,
                                     matcher: Matcher) -> TwitchDownloadStatus:
        disk_check_status = await self._check_space_used()

        if not disk_check_status.is_success:
            return TwitchDownloadStatus(disk_check_status.is_success, message='')
        try:
            file_name = ('{channel_login}_{date}*_{title_slug}.{format}'.replace(
                '*',
                f'+{instruction.start_time.replace(":", "_")}+{instruction.end_time.replace(":", "_")}'))

            if instruction.file_name:
                file_name = file_name.replace('{title_slug}', sanitize_filename(instruction.file_name).rstrip('.mp4'))
            process = await create_subprocess_shell(
                f'twitch-dl download '
                f'-o {file_name} -q source {f"-s {instruction.start_time}" if instruction.start_time else ""} '
                f'{f"-e {instruction.end_time}" if instruction.end_time else ""} -f mp4 {instruction.video_id}',
                stdout=PIPE,
                stderr=PIPE,
                limit=1024 * 1024 * 100  # 100 MB
            )

            try:
                while True:
                    if process.stdout.at_eof() or process.stderr.at_eof():
                        break

                    stdout = (await process.stdout.readline()).decode('utf-8')
                    if stdout:
                        logger.info(f'[twitch downloader] {stdout}')
                        await self._twitch_stdout_handler(matcher, stdout)

                    stderr = (await process.stderr.readline()).decode('utf-8')
                    if stderr:
                        logger.info(f'[twitch downloader] {stderr}')

                    await sleep(.5)

                await process.communicate()
            except ValueError:
                logger.error('Something wrong with stderr stdout operation, but it is very likely is download ready.')

            logger.success(f'Download completed with instruction {instruction}')
            files = [f for f in listdir(getcwd()) if f.endswith('.mp4')]
            if not files:
                return TwitchDownloadStatus(False, 'VideoID 发错了？')

            file_path_to_return = ''
            for file in files:
                creator_folder = PATH_TO_ONEDRIVE + "/" + sanitize_filename(file.split("_")[0])
                file_path_to_return = f'{creator_folder}/{file}'
                if not exists(creator_folder):
                    mkdir(creator_folder)
                move(f'{getcwd()}/{file}', file_path_to_return)

            self.data_found_notification_done = False
            self.ffmpeg_notification_done = False
            self.downloaded_notification_done = False
            self.downloading_notification_done = False
            return TwitchDownloadStatus(
                True,
                message=f'下载好了哦~文件名:\n {files[0]}\n{SHARE_LINK}',
                file_path=file_path_to_return)
        except Exception as err:
            self.data_found_notification_done = False
            self.ffmpeg_notification_done = False
            self.downloaded_notification_done = False
            self.downloading_notification_done = False
            logger.exception('An error occurred')
            return TwitchDownloadStatus(
                False, construct_message_chain(f'Someone tell ', MessageSegment.at(SUPER_USER),
                                               f'there is some problem with my clip. {err.__class__}'))

    async def _twitch_stdout_handler(self, matcher: Matcher, stdout: str):
        if not self.ffmpeg_notification_done and 'ffmpeg' in stdout:
            await matcher.send('在压制咯')
            self.ffmpeg_notification_done = True
        if not self.data_found_notification_done and 'Found:' in stdout:
            await matcher.send(f'找到源了 ~~ {stdout}')
            self.data_found_notification_done = True
        if not self.downloading_notification_done and 'Downloading' in stdout:
            await matcher.send('正在下载切片视频源~')
            self.downloading_notification_done = True
        if not self.downloaded_notification_done and 'Downloaded' in stdout:
            await matcher.send('源检查和下载已完成')
            self.downloaded_notification_done = True
