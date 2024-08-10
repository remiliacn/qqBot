import random
from asyncio import sleep
from os import getcwd
from re import match

from loguru import logger
from wordcloud import WordCloud

BLACKLIST_TAG_NAME = [
    'r-18', 'オリジナル',
    '拘束', '東方', 'did', '女の子', '明日方舟', 'bondage',
    'アークナイツ', '艦', 'tuber', '漫画',
    'project', 'sm', '原神', 'users入り', 'バーチャルyoutuber',
    'clipstudio', 'gag', '原创',
    'アズールレーン', '縛り', '制服', 'fgo', 'vocaloid', 'アイドルマスター', '初音',
    'ホロライブ', 'fate', 'genshin',
    '崩坏', '少女', 'dive', '战双', 'sf'
]

# Genrify similar tag names.
REPLACE_DICT = {
    'ローター': 'バイブ',
    '電マ': 'バイブ',
    'tentacle': '触手',
    '拘束': '緊縛',
    '縛り': '緊縛',
    'ボンデージ': '緊縛',
    '捆绑': '緊縛'
}

MAX_ITERATION = 30


async def get_word_cloud_img(api, user_id):
    xp_dict = {}

    iteration = 0
    json_result = api.user_bookmarks_illust(user_id=user_id)
    next_query = api.parse_qs(json_result.next_url)
    while next_query is not None:
        if iteration > MAX_ITERATION:
            break
        iteration += 1

        logger.info(f'Fetching data: {next_query["max_bookmark_id"]}')
        for result in json_result.illusts:
            tags = result['tags']
            for tag in tags:
                tag_name = tag['name'].lower()
                if tag_name in REPLACE_DICT:
                    tag_name = REPLACE_DICT[tag_name]

                if not match(r'^[a-z_/:]+$', tag_name.strip()):
                    for blacklist_tag in BLACKLIST_TAG_NAME:
                        if blacklist_tag in tag_name:
                            break
                    else:
                        if tag_name not in xp_dict:
                            xp_dict[tag_name] = 1
                        else:
                            xp_dict[tag_name] += 1

        json_result = api.user_bookmarks_illust(**next_query)
        next_query = api.parse_qs(json_result.next_url)
        rand_sleep_time = random.uniform(1.0, 2.0)
        logger.info(f'Sleeping for {rand_sleep_time:.2f}s')
        await sleep(rand_sleep_time)

    print(sorted(xp_dict, key=xp_dict.get, reverse=True)[:50])
    word_cloud = WordCloud(font_path=f'{getcwd()}/Services/util/SourceHanSansSC-Bold.otf',
                           background_color='#fff',
                           max_words=90,
                           width=1920,
                           height=1080).generate_from_frequencies(xp_dict)
    path = f'{getcwd()}/data/pixivPic/{user_id}_pixivcloud.png'
    word_cloud.to_file(path)
    return path
