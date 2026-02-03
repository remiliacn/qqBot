from random import choice, randint
from re import findall
from typing import Union, Optional, Literal

from nonebot.log import logger
from pixivpy3 import PixivError, AppPixivAPI
from pixivpy3.utils import ParsedJson

from awesome.adminControl import group_control
from config import PIXIV_REFRESH_TOKEN


class PixivService:
    def __init__(self):
        self.api = AppPixivAPI()

    def ensure_auth(self) -> bool:
        if not group_control.get_if_authed():
            try:
                self.api.set_auth(
                    access_token=group_control.get_access_token(),
                    refresh_token=PIXIV_REFRESH_TOKEN
                )
                self.api.auth(refresh_token=PIXIV_REFRESH_TOKEN)
                group_control.set_if_authed(True)
                return True
            except PixivError as err:
                logger.warning(f'Pixiv auth failed: {err}')
                return False
        return True

    def reset_auth(self) -> bool:
        group_control.set_if_authed(False)
        try:
            self.api.auth(refresh_token=PIXIV_REFRESH_TOKEN)
            group_control.set_if_authed(True)
            return True
        except PixivError as err:
            logger.warning(f'Pixiv reset auth failed: {err}')
            return False

    async def search_illust(
            self,
            keyword: str,
            sort: Literal["date_desc", "date_asc", "popular_desc", ""] = "popular_desc"
    ) -> Optional[ParsedJson]:
        try:
            if '最新' in keyword:
                result = self.api.illust_ranking('week')
                return result
            else:
                result = self.api.search_illust(word=keyword, sort=sort)
                return result
        except PixivError as err:
            logger.error(f'Pixiv search error: {err}')
            return None

    def get_illust_detail(self, illust_id: Union[str, int]):
        try:
            return self.api.illust_detail(illust_id).illust
        except PixivError as err:
            logger.error(f'Pixiv get illust detail error: {err}')
            return None

    def search_user(
            self,
            username: str,
            sort: Literal["date_desc", "date_asc", "popular_desc", ""] = "popular_desc"
    ):
        try:
            return self.api.search_user(word=username, sort=sort)
        except PixivError as err:
            logger.error(f'Pixiv search user error: {err}')
            return None

    def get_user_illusts(self, user_id: Union[str, int]):
        try:
            return self.api.user_illusts(user_id)
        except PixivError as err:
            logger.error(f'Pixiv get user illusts error: {err}')
            return None

    def get_user_bookmarks(self, user_id: int, max_bookmark_id: Optional[int] = None):
        try:
            if max_bookmark_id:
                return self.api.user_bookmarks_illust(user_id=user_id, max_bookmark_id=max_bookmark_id)
            return self.api.user_bookmarks_illust(user_id=user_id)
        except PixivError as err:
            logger.error(f'Pixiv get user bookmarks error: {err}')
            return None

    def get_user_bookmark_random(self, pixiv_id: int) -> Optional[ParsedJson]:
        if not self.ensure_auth():
            return None

        json_result_list = []
        json_result = self.get_user_bookmarks(pixiv_id)

        if not json_result:
            return None

        if 'error' in json_result:
            if not self.reset_auth():
                return None
            json_result = self.get_user_bookmarks(pixiv_id)
            if not json_result:
                return None

        json_result_list.append(json_result)
        random_loop_time = randint(1, 30)

        for _ in range(random_loop_time):
            next_qs = self.api.parse_qs(json_result.next_url)
            if next_qs is None or 'max_bookmark_id' not in next_qs:
                break
            json_result = self.get_user_bookmarks(pixiv_id, max_bookmark_id=next_qs['max_bookmark_id'])
            if json_result:
                json_result_list.append(json_result)

        return choice(json_result_list) if json_result_list else None

    def search_by_username(self, keyword: str) -> tuple[Union[str, ParsedJson], str]:
        extracted = findall(r'{user=(.*?)}', keyword)
        logger.info(f'Searching artist: {extracted}')

        if not extracted:
            return '未找到该用户。', ''

        username = extracted[0]
        logger.info(f'Artist extracted: {username}')

        json_user = self.search_user(username)
        if not json_user or not json_user.get('user_previews'):
            return f"{username}无搜索结果或图片过少……", ''

        user_id = json_user['user_previews'][0]['user']['id']
        json_result = self.get_user_illusts(user_id)

        if not json_result:
            return f"{username}无搜索结果或图片过少……", ''

        return json_result, username

    def get_ugoira_metadata(self, illust_id: Union[str, int]):
        try:
            return self.api.ugoira_metadata(illust_id)
        except PixivError as err:
            logger.error(f'Pixiv get ugoira metadata error: {err}')
            return None


pixiv_service = PixivService()
