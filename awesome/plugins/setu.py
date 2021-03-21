import random
import re
import time
from datetime import datetime
from os import getcwd
from os.path import exists

import aiohttp
import nonebot
import pixivpy3
from aiocqhttp import MessageSegment

from awesome.adminControl import permission as perm
from awesome.plugins.util.helper_util import anime_reverse_search_response
from config import SUPER_USER, SAUCE_API_KEY, PIXIV_REFRESH_TOKEN
from qq_bot_core import sanity_meter, user_control_module, admin_control, alarm_api

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)
pixiv_api = pixivpy3.ByPassSniApi()
pixiv_api.require_appapi_hosts(hostname='public-api.secure.pixiv.net')
pixiv_api.set_accept_language('en_us')


@nonebot.on_command('色图数据', only_to_me=False)
async def get_setu_stat(session: nonebot.CommandSession):
    setu_stat = sanity_meter.get_keyword_track()[0:10]
    response = ''
    if not setu_stat:
        await session.finish('暂时还无色图数据！')
    for element in setu_stat:
        response += f'关键词：{element[0]} -> hit = {element[1]}\n'

    await session.finish(response)


@nonebot.on_command('理智查询', only_to_me=False)
async def sanity_checker(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' in ctx:
        id_num = ctx['group_id']
    else:
        id_num = ctx['user_id']

    if id_num in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(id_num)
    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(id_num, sanity_meter.get_max_sanity())

    await session.send(f'本群剩余理智为：{sanity}')


@nonebot.on_command('理智补充', only_to_me=False)
async def sanity_refill(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN):
        await session.finish('您没有权限补充理智')

    id_num = 0
    sanity_add = 0
    try:
        id_num = int(session.get('id_num', prompt='请输入要补充的ID'))
        sanity_add = int(session.get('sanity_add', prompt='那要补充多少理智呢？'))
    except ValueError:
        await session.finish('未找到能够补充的对象')

    try:
        sanity_meter.fill_sanity(id_num, sanity=sanity_add)
    except KeyError:
        await session.finish('未找到能够补充的对象')

    await session.finish('补充理智成功！')


@nonebot.on_command('设置色图禁用', only_to_me=False)
async def set_black_list_group(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', True)
        except ValueError:
            await session.finish('这不是数字啊kora')

        await session.finish('你群%s没色图了' % group_id)


@nonebot.on_command('删除色图禁用', only_to_me=False)
async def delete_black_list_group(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', False)
        except ValueError:
            await session.finish('emmm没找到哦~')

        await session.finish('你群%s又有色图了' % group_id)


@nonebot.on_command('色图', aliases='来张色图', only_to_me=False)
async def pixiv_send(session: nonebot.CommandSession):
    if alarm_api.get_alarm():
        await session.finish(
            '警报已升起！请等待解除！\n'
            f'{alarm_api.get_info()}'
        )

    ctx = session.ctx.copy()
    message_id = ctx['message_id']
    if get_privilege(ctx['user_id'], perm.BANNED):
        return

    group_id = ctx['group_id'] if 'group_id' in ctx else -1
    user_id = ctx['user_id']
    if 'group_id' in ctx and not get_privilege(user_id, perm.OWNER):
        if admin_control.get_data(ctx['group_id'], 'banned'):
            await session.finish('管理员已设置禁止该群接收色图。如果确认这是错误的话，请联系bot制作者')

    sanity = -1
    monitored = False
    multiplier = 1
    doMultiply = False

    if group_id in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(group_id)

    elif 'group_id' not in ctx and not get_privilege(user_id, perm.WHITELIST):
        await session.finish('我主人还没有添加你到信任名单哦。请找BOT制作者要私聊使用权限~')

    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(group_id=group_id, sanity=sanity_meter.get_max_sanity())

    if sanity <= 0:
        if group_id not in sanity_meter.remind_dict or not sanity_meter.remind_dict[group_id]:
            sanity_meter.set_remid_dict(group_id, True)
            await session.finish(
                '您已经理智丧失了，不能再查了哟~（小提示：指令理智查询可以帮您查看本群还剩多少理智）'
            )

        return

    if not admin_control.get_if_authed():
        pixiv_api.set_auth(
            access_token=admin_control.get_access_token(),
            refresh_token='iL51azZw7BWWJmGysAurE3qfOsOhGW-xOZP41FPhG-s'
        )
        admin_control.set_if_authed(True)

    is_exempt = admin_control.get_data(group_id, 'exempt') if group_id != -1 else False

    key_word = str(session.get('key_word', prompt='请输入一个关键字进行查询')).lower()

    if key_word in sanity_meter.get_bad_word_dict():
        multiplier = sanity_meter.get_bad_word_dict()[key_word]
        doMultiply = True
        if multiplier > 0:
            await session.send(
                f'该查询关键词在黑名单中，危机合约模式已开启：本次色图搜索将{multiplier}倍消耗理智'
            )

            if multiplier * 2 > 400:
                sanity_meter.set_user_data(user_id, 'ban_count')
                if sanity_meter.get_user_data_by_tag(user_id, 'ban_count') >= 2:
                    user_control_module.set_user_privilege(user_id, 'BANNED', True)
                    await session.send(f'用户{user_id}已被封停机器人使用权限')
                    bot = nonebot.get_bot()
                    await bot.send_private_msg(
                        user_id=SUPER_USER,
                        message=f'User {user_id} has been banned for triggering prtection. Keyword = {key_word}'
                    )


                else:
                    await session.send('本次黑名单搜索已触发群保护机制，下次触发将会导致所有功能禁用。')
                    bot = nonebot.get_bot()
                    await bot.send_private_msg(
                        user_id=SUPER_USER,
                        message=f'User {user_id} triggered protection mechanism. Keyword = {key_word}'
                    )

                del bot
                return
        else:
            await session.send(
                f'该查询关键词在白名单中，支援合约已开启：本次色图搜索将{abs(multiplier)}倍补充理智'
            )

    if key_word in sanity_meter.get_monitored_keywords():
        await session.send('该关键词在主人的监控下，本次搜索不消耗理智，且会转发主人一份√')
        monitored = True
        if 'group_id' in ctx:
            sanity_meter.set_user_data(user_id, 'hit_xp')
            sanity_meter.set_xp_data(key_word)

    elif '色图' in key_word:
        await session.finish(MessageSegment.image(f'file:///{getcwd()}/data/dl/others/QQ图片20191013212223.jpg'))

    elif '屑bot' in key_word:
        await session.finish('你屑你🐴呢')

    json_result = {}

    try:
        if '最新' in key_word:
            json_result = pixiv_api.illust_ranking('week')
        else:
            json_result = pixiv_api.search_illust(
                word=key_word,
                sort="popular_desc"
            )

    except pixivpy3.PixivError:
        await session.finish('pixiv连接出错了！')

    except Exception as err:
        await session.send(f'发现未知错误！错误信息已发送给bot主人分析！\n'
                           f'{err}')

        bot = nonebot.get_bot()
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'Uncaught error while using pixiv search:\n'
                    f'Error from {user_id}\n'
                    f'Keyword = {key_word}\n'
                    f'Exception = {err}')

        return

    # 看一下access token是否过期
    if 'error' in json_result:
        admin_control.set_if_authed(False)
        try:
               
            pixiv_api.auth(refresh_token=PIXIV_REFRESH_TOKEN)
            await session.send('新的P站匿名访问链接已建立……')
            admin_control.set_if_authed(True)

        except pixivpy3.PixivError as err:
            print(err)
            return

    if '{user=' in key_word:
        key_word = re.findall(r'{user=(.*?)}', key_word)
        if key_word:
            key_word = key_word[0]
        else:
            await session.send('未找到该用户。')
            return

        json_user = pixiv_api.search_user(word=key_word, sort="popular_desc")
        if json_user.user_previews:
            user_id = json_user.user_previews[0].user.id
            json_result = pixiv_api.user_illusts(user_id)
        else:
            await session.send(f"{key_word}无搜索结果或图片过少……")
            return

    else:
        json_result = pixiv_api.search_illust(word=key_word, sort="popular_desc")

    if not json_result.illusts or len(json_result.illusts) < 4:
        nonebot.logger.warning(f"未找到图片, keyword = {key_word}")
        await session.send(f"{key_word}无搜索结果或图片过少……")
        return

    sanity_meter.track_keyword(key_word)
    illust = random.choice(json_result.illusts)
    is_r18 = illust.sanity_level == 6
    if not monitored:
        if is_r18:
            sanity_meter.drain_sanity(
                group_id=group_id,
                sanity=2 if not doMultiply else 2 * multiplier
            )
        else:
            sanity_meter.drain_sanity(
                group_id=group_id,
                sanity=1 if not doMultiply else 1 * multiplier
            )

    start_time = time.time()
    path = await download_image(illust)
    try:
        nickname = ctx['sender']['nickname']
    except TypeError:
        nickname = 'null'

    bot = nonebot.get_bot()
    if not is_r18:
        try:
            await session.send(
                f'[CQ:reply,id={message_id}]'
                f'Pixiv ID: {illust.id}\n'
                f'查询关键词：{key_word}\n'
                f'画师：{illust["user"]["name"]}\n' +
                f'{MessageSegment.image(f"file:///{path}")}\n' +
                f'Download Time: {(time.time() - start_time):.2f}s'
            )

            nonebot.logger.info("sent image on path: " + path)

        except Exception as e:
            nonebot.logger.info('Something went wrong %s' % e)
            await session.send('悲，屑TX不收我图。')
            return

    elif is_r18 and (group_id == -1 or admin_control.get_data(group_id, 'R18')):
        await session.send(
            f'[CQ:reply,id={message_id}]'
            f'芜湖~好图来了ww\n'
            f'Pixiv ID: {illust.id}\n'
            f'关键词：{key_word}\n'
            f'画师：{illust["user"]["name"]}\n'
            f'[CQ:image,file=file:///{path}{",type=flash" if not is_exempt else ""}]' +
            f'Download Time: {(time.time() - start_time):.2f}s'
        )

    else:
        if not monitored:
            await session.send('我找到色图了！\n但是我发给我主人了_(:зゝ∠)_')
            await bot.send_private_msg(user_id=SUPER_USER,
                                       message=f"图片来自：{nickname}\n"
                                               f"来自群：{group_id}\n"
                                               f"查询关键词：{key_word}\n" +
                                               f'Pixiv ID: {illust.id}\n' +
                                               f'{MessageSegment.image(f"file:///{path}")}\n' +
                                               f'Download Time: {(time.time() - start_time):.2f}s'
                                       )

    sanity_meter.set_usage(group_id, 'setu')
    if 'group_id' in ctx:
        sanity_meter.set_user_data(user_id, 'setu')

    if monitored and not get_privilege(user_id, perm.OWNER):
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'图片来自：{nickname}\n'
                    f'查询关键词:{key_word}\n'
                    f'Pixiv ID: {illust.id}\n'
                    '关键字在监控中' + f'[CQ:image,file=file:///{path}]'
        )


async def download_image(illust):
    if illust['meta_single_page']:
        if 'original_image_url' in illust['meta_single_page']:
            image_url = illust.meta_single_page['original_image_url']
        else:
            image_url = illust.image_urls['medium']
    else:
        if 'meta_pages' in illust:
            image_url_list = illust.meta_pages
            illust = random.choice(image_url_list)

        image_url = illust.image_urls['medium']

    nonebot.logger.info(f"{illust.title}: {image_url}, {illust.id}")
    image_file_name = image_url.split('/')[-1].replace('_', '')
    path = f'{getcwd()}/data/pixivPic/' + image_file_name

    if not exists(path):
        try:
            async with aiohttp.ClientSession(headers={'Referer': 'https://app-api.pixiv.net/'}) as session:
                async with session.get(image_url) as response:
                    with open(path, 'wb') as out_file:
                        while True:
                            chunk = await response.content.read(1024 ** 3)
                            if not chunk:
                                break
                            out_file.write(chunk)

        except Exception as err:
            nonebot.logger.info(f'Download image error: {err}')

    nonebot.logger.info("PATH = " + path)
    return path

@nonebot.on_command('搜图', only_to_me=False)
async def reverse_image_search(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    args = ctx['raw_message'].split()
    if len(args) != 2:
        await session.finish('¿')

    bot = nonebot.get_bot()
    has_image = re.findall(r'.*?\[CQ:image,file=(.*?\.image)]', args[1])
    if has_image:
        image = await bot.get_image(file=has_image[0])
        url = image['url']
        nonebot.logger.info(f'URL extracted: {url}')
        try:
            response_data = await sauce_helper(url)
            if not response_data:
                await session.finish('阿这~图片辨别率低，请换一张图试试！')
                return

            response = anime_reverse_search_response(response_data)
            await session.send(response)
            return

        except Exception as err:
            await session.send(f'啊这~出错了！报错信息已发送主人debug~')
            await bot.send_private_msg(
                user_id=SUPER_USER,
                message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                        f'搜图功能出错：\n'
                        f'Error：{err}\n'
                        f'出错URL：{url}'
            )


async def sauce_helper(url):
    params = {
        'output_type': 2,
        'api_key': SAUCE_API_KEY,
        'testmode': 0,
        'db': 999,
        'numres': 6,
        'url': url
    }

    response = {}

    async with aiohttp.ClientSession() as client:
        async with client.get(
                'https://saucenao.com/search.php',
                params=params
        ) as page:
            json_data = await page.json()

        if json_data['results']:
            json_data = json_data['results'][0]
            nonebot.logger.info(f'Json data: \n'
                                 f'{json_data}')
            response = ''
            if json_data:
                simlarity = json_data['header']['similarity'] + '%'
                thumbnail = json_data['header']['thumbnail']
                async with client.get(thumbnail) as page:
                    file_name = thumbnail.split('/')[-1]
                    file_name = re.sub(r'\?auth=.*?$', '', file_name)
                    if len(file_name) > 10:
                        file_name = f'{int(time.time())}.jpg'

                    path = f'{getcwd()}/data/lol/{file_name}'
                    if not exists(path):
                        try:
                            with open(path, 'wb') as file:
                                while True:
                                    chunk = await page.content.read(1024 ** 2)
                                    if not chunk:
                                        break

                                    file.write(chunk)
                        except IOError:
                            return {}

                image_content = MessageSegment.image(f'file:///{path}')

                json_data = json_data['data']
                if 'ext_urls' not in json_data:
                    return {}

                pixiv_id = 'Undefined'
                title = 'Undefined'
                author = 'Undefined'

                ext_url = json_data['ext_urls'][0]
                if 'title' not in json_data:
                    if 'creator' in json_data:
                        author = json_data['creator']
                    elif 'author' in json_data:
                        author = json_data['author']
                    else:
                        if 'source' and 'est_time' in json_data:
                            year = json_data['year']
                            part = json_data['part']
                            est_time = json_data['est_time']

                            return {
                                'simlarity': simlarity,
                                'year': year,
                                'part': part,
                                'est_time': est_time,
                                'source': json_data['source'],
                                'thumbnail': image_content
                            }

                        if 'artist' not in json_data:
                            return {}

                        author = json_data['artist']

                elif 'title' in json_data:
                    title = json_data['title']
                    if 'author_name' in json_data:
                        author = json_data['author_name']
                    elif 'member_name' in json_data:
                        author = json_data['member_name']
                        if 'pixiv_id' in json_data:
                            pixiv_id = json_data['pixiv_id']

                response = {
                    'data': image_content,
                    'simlarity': simlarity,
                    'title': title,
                    'author': author,
                    'pixiv_id': pixiv_id,
                    'ext_url': ext_url,
                    'thumbnail': thumbnail
                }

                """
                response += f'{image_content}' \
                            f'图片相似度：{simlarity}\n' \
                            f'图片标题：{title}\n' \
                            f'图片画师：{author}\n' \
                            f'Pixiv ID：{pixiv_id}\n' \
                            f'直链：{ext_url}'
                """

    return response

@nonebot.on_command('ghs', only_to_me=False)
async def get_random_image(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        return

    if admin_control.get_data(ctx['group_id'], 'banned'):
        await session.finish('管理员已设置禁止该群接收色图。如果确认这是错误的话，请联系bot制作者')

    id_num = ctx['group_id']
    user_id = ctx['user_id']
    sanity_meter.set_usage(id_num, 'setu')
    sanity_meter.set_user_data(user_id, 'setu')

    message = await get_random()


async def get_random():
    headers = {
        'Authorization': 'HM9GYMGhY7ccUk7'
    }

    sfw = 'https://gallery.fluxpoint.dev/api/sfw/anime'
    nsfw = 'https://gallery.fluxpoint.dev/api/nsfw/lewd'
    rand_num = random.randint(0, 101)
    is_nsfw = rand_num >= 80

    async with aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
    ) as client:
        async with client.get(nsfw if is_nsfw else sfw) as page:
            json_data = await page.json()

        filename = json_data['file'].split('/')[-1]
        async with client.get(json_data['file']) as image_page:
            path = f'{getcwd()}/data/pixivPic/{filename}'
            if not exists(path):
                with open(path, 'wb') as f:
                    while True:
                        chunk = await image_page.content.read(1024 ** 3)
                        if not chunk:
                            break

                        f.write(chunk)

    return f'[CQ:image,file=file:///{path}{",type=flash" if is_nsfw else ""}]'


@pixiv_send.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg


@set_black_list_group.args_parser
@delete_black_list_group.args_parser
async def _set_group_property(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['group_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('qq组号不能为空')

    session.state[session.current_key] = stripped_arg