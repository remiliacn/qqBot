import nonebot, re
from awesome.plugins.Shadiao import sanity_meter, pcr_api
from awesome.plugins.tweetHelper import tweeter
from awesome.adminControl import shadiaoAdmin
from bilibiliService import bilibiliTopic

tweet = tweeter.tweeter()
admin_control = shadiaoAdmin.Shadiaoadmin()
share_link = 'paryi-my.sharepoint.com/:f:/g/personal/hanayori_paryi_xyz/Em62_uotiDlIohJKvbMWoiQBzutGjbRga1uOXNdmTjEtpA?e=X4hGfT'

@nonebot.on_command('新推', only_to_me=False)
async def get_new_tweet_by_ch_name(session : nonebot.CommandSession):
    key_word = session.get('key_word', prompt='要查谁啊？')
    the_tweet = tweet.get_time_line_from_screen_name(key_word)
    if the_tweet:
        await session.finish(the_tweet)
    else:
        the_tweet = tweet.get_time_line_from_screen_name(key_word)
        await session.finish(the_tweet)

@nonebot.on_command('推特查询', only_to_me=False)
async def bulk_get_new_tweet(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    message = ctx['raw_message']
    args = message.split()
    screen_name = args[1]
    count: str = args[2]
    if count.isdigit():
        resp = tweet.get_time_line_from_screen_name(screen_name, count)
        await session.send(resp)
    else:
        await session.finish('用法错误！应为：\n'
                             '！推特查询 要查询的内容 要前多少条')

@nonebot.scheduler.scheduled_job('interval', seconds=50)
async def send_tweet():
    diff_dict = await tweet.check_update()
    if diff_dict:
        bot = nonebot.get_bot()
        for ch_name in diff_dict:
            group_id_list = tweet.get_tweet_config()[ch_name]['group']
            message = diff_dict[ch_name]
            if message[0:2] == 'RT':
                message = f'=== {ch_name}转发推文说 ===\n' + message
            elif message[0] == '@':
                message = f'=== {ch_name}回了一条推 ===\n' + message
            else:
                message = f'=== {ch_name}发了一条推 ===\n' + message

            nonebot.logger.warning(f'发现新推！来自{ch_name}:\n'
                                f'{message}')

            for element in group_id_list:
                await bot.send_group_msg(group_id=element,
                                         message=message)

    #YouTube部分
    file = open('config/YouTubeNotify.json')
    fl = file.read()
    import json
    youtube_notify_dict = json.loads(str(fl))
    if youtube_notify_dict:
        bot = nonebot.get_bot()
        for elements in youtube_notify_dict:
            if not youtube_notify_dict[elements]['status']:
                if youtube_notify_dict[elements]['retcode'] == 0:
                    try:
                        await bot.send_group_msg(group_id=int(youtube_notify_dict[elements]['group_id']), message='刚才你们让扒的源搞好了~\n视频名称：%s\n如果上传好了的话视频将会出现在\n%s' % (elements, share_link))
                    except Exception as e:
                        nonebot.logger.warning('Something went wrong %s' % e)

                elif youtube_notify_dict[elements]['retcode'] == 1:
                    try:
                        await bot.send_group_msg(group_id=int(youtube_notify_dict[elements]['group_id']), message='有新视频了哦~视频名称：%s' % elements)
                    except Exception as e:
                        nonebot.logger.warning('Something went wrong %s' % e)
            else:
                try:
                    await bot.send_private_msg(user_id=634915227, message=f'源下载失败{elements}')
                except Exception as e:
                    nonebot.logger.warning('Something went wrong %s' % e)

        empty_dict = {}
        with open('E:/Python/qqBot/config/YouTubeNotify.json', 'w+') as f:
            json.dump(empty_dict, f, indent=4)

        file.close()

    #PCR部分
    if await pcr_api.if_new_releases():
        bot = nonebot.get_bot()
        news = await pcr_api.get_content()
        await bot.send_group_msg(group_id=1081267415 ,message=news)
        

    if sanity_meter.happy_hours:
        sanity_meter.fill_sanity(sanity=5)
    else:
        sanity_meter.fill_sanity(sanity=1)

    sanity_meter.make_a_json('config/stats.json')
    sanity_meter.make_a_json('config/setu.json')

@nonebot.on_command('b站话题', aliases={'B站话题', 'btopic'}, only_to_me=False)
async def get_bilibili_topic(session : nonebot.CommandSession):
    key_word = session.get('key_word', prompt='要什么的话题呢？')
    await session.send('如果动态内容有图片的话这可能会花费一大段时间。。请稍后……')
    topic = bilibiliTopic.Bilibilitopic(topic=key_word)
    response = topic.get_content()
    if response != '':
        await session.send(response)
        return

    await session.send('emmm, 好像没有内容？要不换个话题试试？')

@get_bilibili_topic.args_parser
@get_new_tweet_by_ch_name.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg