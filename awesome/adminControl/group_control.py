from os import listdir, path, remove
from os.path import exists
from sqlite3 import OperationalError
from typing import Optional, Union

from nonebot import logger
from nonebot.adapters.onebot.v11 import MessageSegment

from Services.util.common_util import calculate_sha1
from awesome.Constants.path_constants import LOL_FOLDER_PATH
from model.common_model import Status
from util.db_utils import execute_db

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
        self._init_group_setting()

    def _init_group_setting(self):
        execute_db(
            self.group_quotes_path,
            """
            create table if not exists group_settings
            (
                group_id     varchar(20) unique on conflict ignore,
                is_banned    boolean default false,
                is_enabled   boolean default true,
                allow_r18    boolean default false,
                recall_catch boolean default false,
                nlp_process    boolean default true,
                memory_enabled boolean default false
            )
            """
        )
        execute_db(
            self.group_quotes_path,
            """
            create table if not exists quotes
            (
                "cq_image" text unique on conflict ignore,
                "qq_group" text,
                "file_hash" text,
                "notes"    text
            )
            """
        )

        execute_db(
            self.group_quotes_path,
            "create index if not exists idx_quotes_qq_group on quotes(qq_group)"
        )
        execute_db(
            self.group_quotes_path,
            "create index if not exists idx_quotes_qq_group_notes on quotes(qq_group, notes)"
        )
        execute_db(
            self.group_quotes_path,
            "create index if not exists idx_quotes_file_hash on quotes(file_hash)"
        )
        execute_db(
            self.group_quotes_path,
            "create index if not exists idx_group_settings_group_id on group_settings(group_id)"
        )

        column_backfill_data = [('file_hash', 'text'), ('notes', 'text')]
        for data in column_backfill_data:
            try:
                execute_db(
                    self.group_quotes_path,
                    f"""
                    ALTER TABLE quotes ADD COLUMN {data[0]} {data[1]};
                    """
                )
            except OperationalError as err:
                logger.warning(
                    f'Failed to add column, but it is probably fine because it is already existed. {err.__class__}')

    def _check_if_file_exists_in_db(self, file_name: str) -> bool:
        result = execute_db(
            self.group_quotes_path,
            """
            select *
            from quotes
            where cq_image = ?
            """, (file_name,), fetch_one=True
        )

        return result is not None and result

    def _check_if_hash_collided(self, file_hash: str) -> bool:
        result = execute_db(
            self.group_quotes_path,
            """
            select *
            from quotes
            where file_hash = ?
            """, (file_hash,), fetch_one=True
        )

        return result is not None and result

    def group_quote_startup_sanity_check(self):
        for file in listdir(LOL_FOLDER_PATH):
            quote_file_abs_path = path.join(LOL_FOLDER_PATH, file).replace('\\', '/')
            if not self._check_if_file_exists_in_db(quote_file_abs_path):
                remove(quote_file_abs_path)
                logger.info(f'Deleting file {quote_file_abs_path} because it does not exist in db.')

        all_results = execute_db(
            self.group_quotes_path,
            """
            select *
            from quotes
            """, fetch_all=True
        )

        for entry in all_results:
            if entry:
                cq_image, qq_group, file_hash, _notes = entry
                self._backfill_file_sha1_hash(cq_image, file_hash)
                if not exists(cq_image):
                    logger.info(f'File no longer exist, deleting entry: {cq_image}')
                    execute_db(
                        self.group_quotes_path,
                        """
                        delete
                        from quotes
                        where cq_image = ?
                        """, (cq_image,)
                    )

    def _backfill_file_sha1_hash(self, cq_image, file_hash):
        if not file_hash and exists(cq_image):
            logger.debug(f'Backfilling quote file hash: {cq_image}')
            file_hash = calculate_sha1(cq_image)
            execute_db(
                self.group_quotes_path,
                """
                update quotes
                set file_hash = ?
                where cq_image = ?
                """, (file_hash, cq_image)
            )

    def add_quote(self, group_id: Union[int, str], quote: str, notes: str) -> Status:
        if isinstance(group_id, int):
            group_id = str(group_id)

        if self._check_if_hash_collided(calculate_sha1(quote)):
            remove(quote)
            return Status(False, '语录已被添加')

        execute_db(
            self.group_quotes_path,
            f"""
            insert into quotes (cq_image, qq_group, file_hash, notes) values (?, ?, ?, ?)
            """, (quote, group_id, calculate_sha1(quote), notes.strip())
        )
        return Status(True, '整好了~')

    def transfer_group_quote(self, target_group_id: Union[int, str], original_group_id: Union[int, str]):
        if isinstance(target_group_id, int):
            target_group_id = str(target_group_id)

        if isinstance(original_group_id, int):
            original_group_id = str(original_group_id)

        execute_db(
            self.group_quotes_path,
            """
            update quotes
            set qq_group = ?
            where qq_group = ?
            """, (target_group_id.strip(), original_group_id.strip())
        )

    def get_group_quote(self, group_id: Union[int, str], notes: Optional[str] = None) -> Status:
        group_id_str = str(group_id)
        notes_str = notes.strip() if notes else ""

        query_sql = (
            "select cq_image, notes from quotes "
            "where qq_group = ? "
        )
        params: list[str] = [group_id_str]

        if notes_str:
            query_sql += "and notes like ? "
            params.append(f"%{notes_str}%")

        query_sql += "order by random() limit 1;"

        data = execute_db(self.group_quotes_path, query_sql, tuple(params), fetch_one=True)
        if not data:
            return Status(False, MessageSegment.text('该群没有语录哦'))

        cq_image, notes_db = data

        from util.helper_util import construct_message_chain
        return Status(True, construct_message_chain(MessageSegment.image(cq_image), notes_db or ''))

    def clear_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        execute_db(
            self.group_quotes_path,
            f"""
            delete from quotes where qq_group='{group_id}'
            """
        )
        return True

    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query_result = execute_db(
            self.group_quotes_path,
            f"""
            select count(*) from quotes where qq_group='{group_id}'
            """, fetch_one=True
        )

        return query_result[0]

    def set_group_permission(self, group_id: Union[int, str], tag: str, stat: bool):
        group_id = str(group_id)

        execute_db(
            self.group_quotes_path,
            f"""
            insert or replace into group_settings 
            (group_id, {tag}) values (
                ?, ?
            )
            """, (group_id, stat)
        )

    def get_group_permission(self, group_id: Union[int, str], tag: str) -> bool:
        if isinstance(group_id, int):
            group_id = str(group_id)

        result = execute_db(
            self.group_quotes_path,
            f"""
            select {tag} from group_settings where group_id = ? limit 1;
            """, (group_id,), fetch_one=True
        )

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
