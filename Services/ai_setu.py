import random
import re
import time
import uuid
from asyncio import gather
from base64 import decodebytes
from os import getcwd, remove
from typing import List, Union
from urllib.parse import quote, unquote

from loguru import logger

from Services.util.common_util import HttpxHelperClient
from config import NOVEL_AI_KEY, NOVEL_AI_BEARER
from qq_bot_core import setu_control


class AIImageGenerator:
    def __init__(self):
        self.request_url = 'https://api.novelai.net/ai/generate-image'
        self.login_url = 'https://api.novelai.net/user/login'
        self.header = {
            'Authorization': NOVEL_AI_BEARER
        }

        self._size_list = [(512, 768), (640, 640), (768, 512)]
        self._sampler_list = ['k_euler', 'k_euler_ancestral']
        self.setu_connection = setu_control.setu_db_connection
        self.client = HttpxHelperClient()

    def _init_ai_setu_database(self):
        self.setu_connection.execute(
            """
            create table if not exists ai_setu_rating_holder
            (
                hit      int  default 0,
                image    text default '',
                uid      varchar(255) not null
                    constraint ai_setu_rating_holder_pk
                        primary key,
                keywords varchar(255) not null,
                voted    text default ''
            );
            
            create unique index if not exists ai_setu_rating_holder_uid_uindex
                on ai_setu_rating_holder (uid);

            create table if not exists ai_setu_tag_confident
            (
                tag          varchar(255)
                    constraint ai_setu_tag_confident_pk
                        primary key,
                train_count  int default 0,
                last_updated int default 0
            );
            
            create unique index if not exists ai_setu_tag_confident_tag_uindex
                on ai_setu_tag_confident (tag);

            create table if not exists setu_keyword_replacer
            (
                original_keyword varchar(255) not null
                    constraint setu_keyword_replacer_pk
                        primary key,
                replaced_keyword varchar(255) not null
            );
            
            create unique index if not exists setu_keyword_replacer_original_keyword_uindex
                on setu_keyword_replacer (original_keyword);
            """
        )

        self.setu_connection.execute()

    async def remove_replace_words(self, arg: str):
        self.setu_connection.execute(
            """
            delete from setu_keyword_replacer where original_keyword = ?
            """, (arg,)

        )
        self.setu_connection.commit()

    async def add_high_confident_word(self, args: List[str]):
        self.setu_connection.execute(
            """
            insert or replace into setu_keyword_replacer (original_keyword, replaced_keyword) values (
                ?, ?
            )
            """, (args[0].strip(), args[1].strip())
        )

        self.setu_connection.commit()

    async def replace_high_confident_word(self, keyword: str) -> str:
        result = self.setu_connection.execute(
            """
            select replaced_keyword from setu_keyword_replacer where original_keyword = ? limit 1;
            """, (re.sub(r'[{\[\]}]', '', keyword.strip().lower()),)
        ).fetchone()

        if result is not None and result[0] is not None:
            return result[0] if isinstance(result, tuple) or isinstance(result, list) else result

        return ''

    async def reverse_get_high_confident_word(self, en_tag: str) -> str:
        result = self.setu_connection.execute(
            """
            select original_keyword from setu_keyword_replacer where LOWER(replaced_keyword) like ? limit 1;
            """, (en_tag.strip().lower(),)
        ).fetchone()

        return result if isinstance(result, str) else result[0] if result is not None and result[0] is not None else ''

    async def delete_holder_data(self):
        result = self.setu_connection.execute(
            """
            select image from ai_setu_rating_holder where hit <= 1 and length(image) > 5
            """
        ).fetchall()

        for path in result:
            if path:
                logger.info(f'Deleting file in path: {path[0]}')
                remove(path[0])

        self.setu_connection.execute(
            """
            delete from ai_setu_rating_holder where hit <= 1;
            """
        )

        self.setu_connection.commit()

    async def _get_last_update_cache_tag_confident(self, tag: str):
        result = self.setu_connection.execute(
            """
            select last_updated from ai_setu_tag_confident where LOWER(tag) like ? limit 1;
            """, (tag.lower().strip(),)
        ).fetchone()

        return result if isinstance(result, int) else result[0] if result is not None and result[0] is not None else 0

    async def set_cache_tag_confident(self, tag: str, train_count):
        self.setu_connection.execute(
            """
            insert or replace into ai_setu_tag_confident (tag, train_count, last_updated) values (
                ?, ?,  ?
            )
            """, (tag.lower().strip(), train_count, int(time.time()))
        )
        self.setu_connection.commit()

    async def get_cache_tag_confident(self, tag: str):
        result = self.setu_connection.execute(
            """
            select train_count from ai_setu_tag_confident where tag = ? limit 1;
            """, (tag,)
        ).fetchone()

        return result if isinstance(result, int) else result[0] if result is not None and result[0] is not None else -1

    async def _get_tag_confident(self, tag: str):
        tag = unquote(tag).strip().lower()
        cache_train_count = await self.get_cache_tag_confident(tag)

        if cache_train_count > 0:
            return tuple((tag, cache_train_count))

        request = await self.client.get(
            f'https://api.novelai.net/ai/generate-image/'
            f'suggest-tags?model=nai-diffusion&prompt={tag}',
            headers=self.header,
            timeout=None
        )

        request_json = request.json()
        if request_json and 'tags' in request_json and request_json['tags']:
            request_resp_tag = request_json['tags']
            for tag_result in request_resp_tag:
                if tag in tag_result['tag'].lower() \
                        or tag.replace(' ', '') in tag_result['tag'].lower():
                    await self.set_cache_tag_confident(tag, tag_result['count'])
                    return tuple((tag_result['tag'], tag_result['count']))
            else:
                logger.info(f'Target missed: {request_json}')
                return f'{tag}，未命中高训练集关键字，可能该tag的权重将降低。\n'

        return f'{tag}未命中高训练集关键字，可能该tag的权重将降低。\n'

    async def get_tag_confident_worker(self, tags: List[str]):
        tasks_list = []
        for tag in tags:
            if tag:
                tasks_list.append(
                    self._get_tag_confident(
                        quote(tag.strip().replace('{', '').replace('}', '').replace('_', ' '))
                    )
                )

        running_result = await gather(*tasks_list)
        response = ''
        for result in running_result:
            if result is not None:
                if isinstance(result, tuple):
                    response += f'{result[0]}，绘图训练数：{result[1]}\n'
                else:
                    response += str(result)

        return response

    async def up_vote_uuid(self, uid: str, user_id: Union[str, int]) -> Union[None, List[str]]:
        result = self.setu_connection.execute(
            """
            select keywords, voted from ai_setu_rating_holder where uid = ? limit 1;
            """, (uid,)
        ).fetchone()

        if result is None or result[0] is None:
            return None

        voted_users = result[1].split(',')
        if str(user_id) in voted_users:
            return 'DUPLICATED'

        self.setu_connection.execute(
            f"""
            insert or replace into ai_setu_rating_holder (uid, keywords, voted, hit) values (
                ?, 
                coalesce((select keywords from ai_setu_rating_holder where uid = ?), ''), 
                coalesce((select voted from ai_setu_rating_holder where uid = ?) || ',{user_id}', '{user_id}'),
                coalesce((select hit from ai_setu_rating_holder where uid = ?), 0) + 1
            )
            """, (uid, uid, uid, uid)
        )

        result_list = re.split(r',\d*', result[0])
        self.setu_connection.commit()

        return result_list

    async def get_all_banned_words(self) -> list:
        result = self.setu_connection.execute(
            """
            select original_keyword from setu_keyword_replacer where replaced_keyword = '|';
            """
        ).fetchall()

        return [r[0] for r in result]

    async def _set_uuid_and_user_prompt(self, uid: str, keywords: str, path: str):
        self.setu_connection.execute(
            """
            insert into ai_setu_rating_holder (uid, keywords, image) values (
                ?, ?, ?
            )
            """, (uid, keywords, path)
        )

        self.setu_connection.commit()

    async def get_ai_generated_image(self, keywords: str, seed: int) -> (str, str, str):
        size = random.choice(self._size_list)
        sampler = random.choice(self._sampler_list)

        request = await self.client.post(url=self.request_url, headers=self.header, json={
            'input': 'masterpiece, best quality, ' + keywords,
            'model': 'nai-diffusion',
            'parameters': {
                "width": size[0],
                "height": size[1],
                "scale": 11,
                "sampler": sampler,
                "steps": 28,
                "seed": seed,
                "n_samples": 1,
                "ucPreset": 0,
                "uc": "nsfw, lowres, bad anatomy, bad hands, text, error, "
                      "missing fingers, extra digit, fewer digits, cropped, "
                      "worst quality, low quality, normal quality, jpeg artifacts, "
                      "signature, watermark, username, blurry"
            }
        }, timeout=None)

        path = f'{getcwd()}/data/pixivPic/'
        if request.status_code == 201:
            image_data = request.text[27:]
            path += str(int(time.time_ns())) + '.png'
            with open(path, 'wb') as file:
                file.write(decodebytes(str.encode(image_data)))

            uid = str(uuid.uuid4())
            await self._set_uuid_and_user_prompt(uid, keywords, path)
            return path, uid, sampler
        else:
            await self.relogin()

        return '', None, sampler

    async def relogin(self):
        result = await self.client.post(self.login_url, json={
            'key': NOVEL_AI_KEY
        })
        authorization = result.json()['accessToken']
        self.header['Authorization'] = f'Bearer {authorization}'
