import json
import os
import re
import shutil
import sys

import requests
import youtube_dl
from nonebot.log import logger

from config import ffmpeg_path, path_temp, path_export


def main():
    if not get_status():
        logger.warning('There is one task running.')
        return

    var = sys.argv
    logger.warning(var)
    if len(var) == 1:
        logger.warning('Missing arguments!')
        exit(1)

    setting = var[1]

    if setting == 'single':
        video_id = var[2]
        group_id = var[3]
        register_false()
        download_video(video_id, 'others', group_id, True)

    else:
        user_in_dict = get_config()
        if not user_in_dict:
            logger.warning('Init failed when trying to download videos.')
            register_true()
            exit(-1)

        register_false()
        for youtube_user in user_in_dict:
            try:
                logger.warning(f'Getting first video for: {youtube_user}')
                get_first_video(
                    user_in_dict[youtube_user]['channel'],
                    youtube_user,
                    user_in_dict[youtube_user]['qqGroup'],
                    user_in_dict
                )
            except Exception as err:
                logger.warning(f'Unknown error occurred for {youtube_user}: {err}')

    if not get_status():
        logger.warning('Exiting YouTube downloader...')
        register_true()


def register_true():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    status_dict['status'] = True
    with open('data/started.json', 'w+') as f:
        json.dump(status_dict, f, indent=4)


def register_false():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    status_dict['status'] = False
    with open('data/started.json', 'w+') as f:
        json.dump(status_dict, f, indent=4)


def get_status():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    return status_dict['status']


def get_config() -> dict:
    file = open('config/downloader.json', 'r+')
    fl = file.read()
    import json
    try:
        download_dict = json.loads(str(fl))
    except Exception as e:
        logger.warning('Something went wrong when getting download config. %s' % e)
        return {}

    return download_dict


def get_first_video(channel_id: str, name: str, group_id, user_dict: dict):
    headers = {
        'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/84.0.4147.125 Safari/537.36',
        'Referer': 'https://www.youtube.com/'
    }
    page = requests.get(
        f'https://www.youtube.com/channel/{channel_id}/videos',
        headers=headers
    )
    content = re.findall(r'ytInitialData = ({.*?});', page.text)
    if content:
        content = content[0]

    try:
        json_data = json.loads(content)
    except Exception as err:
        logger.warning(f'Getting video ID failed for {name}. {err}')
        return

    try:
        video_tab = json_data['contents']['twoColumnBrowseResultsRenderer']['tabs'][1]
        video_tab_inner = video_tab['tabRenderer']['content']['sectionListRenderer']
        video_tab_inner = video_tab_inner['contents'][0]['itemSectionRenderer']['contents']
        first_video_outer = video_tab_inner[0]['gridRenderer']['items'][0]['gridVideoRenderer']
        first_video_id = first_video_outer['videoId']
        if 'publishedTimeText' not in first_video_outer:
            logger.warning(f'The video is live right now for {name}')
            return

        publish_time = first_video_outer['publishedTimeText']['simpleText']
        enabled = user_dict[name]['enabled']
        if 'hours ago' not in publish_time and enabled:
            logger.warning('Not a recent video or the video is not yet converted.')
            return
        else:
            if enabled:
                time = re.findall(r'(\d+) hours ago', publish_time)
                if time:
                    logger.warning(f'{name} - This video is published {time[0]} hours ago')
                    if int(time[0]) < 2:
                        logger.warning('The video may not be fully converted, aborting...')
                        return

    except KeyError as err:
        logger.warning('Something has happened with %s... Error Message: %s' % (name, err))
        return

    video_id_temp = user_dict[name]["videoID"] if 'videoID' in user_dict[name] else ''
    if first_video_id == video_id_temp:
        logger.warning('Download is already finished. This is the test from videoID test.')
        return

    logger.warning('Current Video ID is: %s' % first_video_id)
    enabled = user_dict[name]['enabled']
    download_video(first_video_id, name, group_id, enabled)


def download_video(video_id: str, name: str, groupID, enable: bool):
    register_false()
    youtube_link = "https://www.youtube.com/watch?v=%s" % video_id

    ydl_opts = {
        'format': 'bestvideo+bestaudio',  # 扒取视频的最好清晰度
        'noplaylist': True
    }
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.cache.remove()
            videoTitle_temp = ydl.extract_info(youtube_link, download=False).get('title')
            video_title = videoTitle_temp.replace('|', '').replace('/', '').replace('?', '')
            video_title = video_title.replace('>', '').replace('<', '').replace(':', '')
            video_title = video_title.replace('*', '').replace('\\', '').replace('"', '')


    except youtube_dl.utils.ExtractorError:
        logger.warning('Current Video is not available yet')
        return

    video_path = path_export + name + '/' + video_title + '.mp4'
    video_path_temp = path_temp + name + '/' + video_title + '.mp4'
    logger.warning('Downloading in %s' % video_path_temp)

    if not os.path.exists(path_export + name + '/'):
        os.makedirs(path_export + name + '/')

    if not os.path.exists(path_temp + name + '/'):
        os.makedirs(path_temp + name + '/')

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]',
        'outtmpl': '%s' % video_path_temp,  # 下载地址
        'noplaylist': True,
        'ffmpeg_location': ffmpeg_path,  # ffmpeg.exe路径
        'prefer_ffmpeg': True,
        'cachedir': False,
        'merge_output_format' : 'mp4'
    }

    # 查看是否视频已经被下载
    if not os.path.exists(video_path) and enable:
        logger.warning(f"Missing video: {video_title}")
        logger.warning('Download will be starting shortly.\nVideo ID: %s' % video_id)
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_link])

            logger.warning('Download is completed.\nVideo title: %s' % video_title)
            logger.warning('Moving video to: ' + video_path)
            shutil.move(video_path_temp, video_path)

            upload_status(name, videoTitle_temp, video_id, groupID, retcode=0)

        except Exception as e:
            logger.warning(f'Download failed for {name}, will try again later... {e}')

    # 如果只是提醒，则返回一个retcode=1，这个retcode在我的机器人中意味着未下载，只提醒。
    # retcode=0代表着已下载，并需要提醒
    # retcode=-1代表下载出错，需要重试

    elif not enable:
        upload_status(name, videoTitle_temp, video_id, groupID, retcode=1)

    else:
        logger.warning('Unhandled stiuation.')


def upload_status(ch_name: str, video_name: str, video_id: str, group_id, retcode: int):
    file = open('config/YouTubeNotify.json', 'r')
    fl = file.read()
    downloaded_dict = json.loads(str(fl))
    downloaded_dict[video_name] = {
        "status": False,
        "group_id": group_id,
        "retcode": retcode
    }

    signal_downloader_register(video_id, ch_name, retcode)

    with open('config/YouTubeNotify.json', 'w+') as f:
        json.dump(downloaded_dict, f, indent=4)


def signal_downloader_register(video_id: str, name: str, retcode: int):
    if name != 'others' and retcode != -1:
        user_dict = get_config()
        if user_dict[name]['videoID'] != video_id:
            user_dict[name]['videoID'] = video_id

            with open('config/downloader.json', 'w+') as f:
                json.dump(user_dict, f, indent=4)


if __name__ == '__main__':
    main()
