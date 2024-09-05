import sqlite3
from os import listdir, path, remove
from os.path import exists
from typing import Union

from nonebot import logger

from Services.util.common_util import calculate_sha1
from model.common_model import Status
from awesome.Constants.path_constants import LOL_FOLDER_PATH

GROUP_PERMISSION_DEFAULT = {
    'IS_BANNED': False,
    'IS_ENABLED': True,
    'ALLOW_R18': False,
    'RECALL_CATCH': False,
    'NLP_PROCESS': False,
    'RATE_LIMITED': False
}


class GroupControlModule:
    def __init__(self):
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False

        self.repeat_dict = {}

        self.group_quotes_path = 'data/db/quotes.db'

        self.group_info_db = sqlite3.connect(self.group_quotes_path)
        self._init_group_setting()

    def _init_group_setting(self):
        self.group_info_db.execute(
            """
            create table if not exists group_settings (
                group_id varchar(20) unique on conflict ignore,
                is_banned boolean default false,
                is_enabled boolean default true,
                allow_r18 boolean default false,
                recall_catch boolean default false,
                nlp_process boolean default true
            )
            """
        )
        self.group_info_db.execute(
            """
            create table if not exists quotes (
                "cq_image" text unique on conflict ignore, 
                "qq_group" text,
                "file_hash" text
            )
            """
        )
        self.group_info_db.commit()
        try:
            self.group_info_db.execute(
                """
                ALTER TABLE quotes ADD COLUMN file_hash text;
                """
            )
            self.group_info_db.commit()
        except Exception as err:
            logger.warning(
                f'Failed to add column, but it is probably fine because it is already existed. {err.__class__}')

    def _check_if_file_exists_in_db(self, file_name: str) -> bool:
        result = self.group_info_db.execute(
            """
            select * from quotes where cq_image = ?
            """, (file_name,)
        ).fetchone()

        return result is not None and result

    def _check_if_hash_collided(self, file_hash: str) -> bool:
        result = self.group_info_db.execute(
            """
            select * from quotes where file_hash = ?
            """, (file_hash,)
        ).fetchone()

        return result is not None and result

    def group_quote_startup_sanity_check(self):
        for file in listdir(LOL_FOLDER_PATH):
            quote_file_abs_path = path.join(LOL_FOLDER_PATH, file).replace('\\', '/')
            if not self._check_if_file_exists_in_db(quote_file_abs_path):
                remove(quote_file_abs_path)
                logger.info(f'Deleting file {quote_file_abs_path} because it does not exist in db.')

        all_results = self.group_info_db.execute(
            """
            select * from quotes
            """
        ).fetchall()

        for entry in all_results:
            if entry:
                cq_image, qq_group, file_hash = entry
                self._backfill_file_sha1_hash(cq_image, file_hash)

    def _backfill_file_sha1_hash(self, cq_image, file_hash):
        if not file_hash and exists(cq_image):
            logger.debug(f'Backfilling quote file hash: {cq_image}')
            file_hash = calculate_sha1(cq_image)
            self.group_info_db.execute(
                """
                update quotes set file_hash = ? where cq_image = ?
                """, (file_hash, cq_image)
            )
            self.group_info_db.commit()

    def add_quote(self, group_id: Union[int, str], quote: str) -> Status:
        if isinstance(group_id, int):
            group_id = str(group_id)

        if self._check_if_hash_collided(calculate_sha1(quote)):
            remove(quote)
            return Status(False, '语录已被添加')

        self.group_info_db.execute(
            f"""
            insert into quotes (cq_image, qq_group, file_hash) values (?, ?, ?)
            """, (quote, group_id, calculate_sha1(quote))
        )
        self.group_info_db.commit()
        return Status(True, '整好了~')

    def transfer_group_quote(self, target_group_id: Union[int, str], original_group_id: Union[int, str]):
        if isinstance(target_group_id, int):
            target_group_id = str(target_group_id)

        if isinstance(original_group_id, int):
            original_group_id = str(original_group_id)

        self.group_info_db.execute(
            """
            update quotes set qq_group = ? where qq_group = ?
            """, (target_group_id.strip(), original_group_id.strip())
        )
        self.group_info_db.commit()

    def get_group_quote(self, group_id: Union[int, str]) -> Status:
        if isinstance(group_id, int):
            group_id = str(group_id)

        query = self.group_info_db.execute(
            f"""
            select cq_image from quotes where qq_group = '{group_id}' order by random() limit 1;
            """
        ).fetchone()

        if query is None or query[0] is None:
            return Status(False, '本群还没有语录哦~')

        return Status(True, query[0])

    def clear_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        self.group_info_db.execute(
            f"""
            delete from quotes where qq_group='{group_id}'
            """
        )
        self.group_info_db.commit()
        return True

    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query_result = self.group_info_db.execute(
            f"""
            select count(*) from quotes where qq_group='{group_id}'
            """
        )

        return query_result.fetchone()[0]

    def set_group_permission(self, group_id: Union[int, str], tag: str, stat: bool):
        group_id = str(group_id)

        self.group_info_db.execute(
            f"""
            insert or replace into group_settings 
            (group_id, {tag}) values (
                ?, ?
            )
            """, (group_id, stat)
        )
        self.group_info_db.commit()

    def get_group_permission(self, group_id: Union[int, str], tag: str) -> bool:
        if isinstance(group_id, int):
            group_id = str(group_id)

        result = self.group_info_db.execute(
            f"""
            select {tag} from group_settings where group_id = ? limit 1;
            """, (group_id,)
        ).fetchone()

        if result is None or result[0] is None:
            return GROUP_PERMISSION_DEFAULT[tag.upper()]

        return result[0]

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_access_token(self):
        return self.access_token

    def get_if_authed(self):
        return self.auth_stat

    def set_if_authed(self, stats):
        self.auth_stat = stats
