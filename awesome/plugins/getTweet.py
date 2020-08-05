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
    the_tweet = tweet.get_new_tweet_by_ch_name(key_word)
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

@nonebot.scheduler.scheduled_job('interval', seconds=49)
async def send_tweet():
    # 跟推部分
    print('***********Doing auto send tweet....*****************')
    old_tweet_list = tweet.get_tweet_list()
    print('OLD TWEET LIST:' + str(old_tweet_list))
    new_tweet_list = tweet.get_every_new_tweet_in_list()
    print('NEW TWEET LIST:' + str(new_tweet_list))
    print('------------------------------------------------------')

    bot = nonebot.get_bot()
    diff_list = await check_new_tweets(old_tweet_list, new_tweet_list)
    if diff_list:
        for ch_name in diff_list:
            tweet.set_new_tweet_by_ch_name(ch_name=ch_name, tweet=new_tweet_list[ch_name])
            nonebot.logger.warning(f'发现新推！ [来自{ch_name}]\n{new_tweet_list[ch_name]}')
            if re.match(r'^RT', new_tweet_list[ch_name]):
                response = '------%s转了一个推：-----\n%s' % (ch_name, new_tweet_list[ch_name])
            elif re.match(r'^@', new_tweet_list[ch_name]):
                if re.match(r'.*?む', ch_name):
                    continue
                response = '------%s回复了一条推：-----\n%s' % (ch_name, new_tweet_list[ch_name])
            else:
                response = '------%s发新推啦！-----\n%s' % (ch_name, new_tweet_list[ch_name])

            group_id_dict = tweet.get_group_id_dict()
            group_id_list = group_id_dict[ch_name]
            if group_id_list:
                for group_id in group_id_list:
                    await bot.send_group_msg(group_id=group_id, message=response)

    #YouTube部分
    file = open('config/YouTubeNotify.json')
    fl = file.read()
    import json
    youtube_notify_dict = json.loads(str(fl))
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

    if youtube_notify_dict:
        empty_dict = {}
        with open('E:/Python/qqBot/config/YouTubeNotify.json', 'w+') as f:
            json.dump(empty_dict, f, indent=4)

        file.close()

    #PCR部分
    if await pcr_api.if_new_releases():
        news = await pcr_api.get_content()
        await bot.send_group_msg(group_id=1081267415 ,message=news)
        

    if sanity_meter.happy_hours:
        sanity_meter.fill_sanity(sanity=5)
    else:
        sanity_meter.fill_sanity(sanity=1)

    sanity_meter.make_a_json('config/stats.json')
    sanity_meter.make_a_json('config/setu.json')

    del bot, youtube_notify_dict

async def check_new_tweets(old_tweet_list, new_tweet_list) -> dict:
    ch_name_dict = {}
    for ch_name in old_tweet_list:
        if old_tweet_list[ch_name] != new_tweet_list[ch_name]:
            if not (new_tweet_list[ch_name] == '' or new_tweet_list[ch_name] == '转发动态'):
                ch_name_dict[ch_name] = new_tweet_list[ch_name]

    return ch_name_dict

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