from typing import Union, List, Tuple, Optional

from awesome.Constants.function_key import USER_XP
from util.db_utils import fetch_one_or_default, execute_db


class SetuFunctionControl:
    def __init__(self):
        self.blacklist_freq_keyword = ('R-18', 'オリジナル', '女の子')
        self.ordered_stat = {}

        self.setu_db_path = 'data/db/setu.db'
        self.stat_db_path = 'data/db/stats.db'

        self._init_stat_db()
        self._init_setu_db()

    def _init_stat_db(self):
        execute_db(
            self.stat_db_path,
            """
            create table if not exists user_activity_count
            (
                user_id  varchar(20) not null,
                tag      varchar(20) not null,
                hit      integer     not null default 0,
                nickname varchar(200),
                unique (user_id, tag) on conflict ignore
            );
            """
        )
        execute_db(
            self.stat_db_path,
            """
            create table if not exists group_activity_count
            (
                group_id varchar(20) not null,
                tag      varchar(20) not null,
                hit      integer     not null default 0,
                unique (group_id, tag) on conflict ignore
            );
            """
        )
        execute_db(
            self.stat_db_path,
            """
            create table if not exists global_stat
            (
                keyword varchar(150) unique on conflict ignore,
                hit     integer not null
            );
            """
        )
        execute_db(
            self.stat_db_path,
            """
            create table if not exists monitor_xp_data
            (
                keyword varchar(150) unique on conflict ignore,
                hit     integer not null default 0
            );
            """
        )
        execute_db(
            self.stat_db_path,
            """
            create table if not exists user_xp_count
            (
                user_id  varchar(20)  not null,
                keyword  varchar(150) not null,
                hit      integer      not null default 0,
                nickname varchar(255),
                unique (user_id, keyword) on conflict ignore
            );
            """
        )

    def _init_setu_db(self):
        execute_db(
            self.setu_db_path,
            """
            create table if not exists bad_words
            (
                keyword text unique on conflict ignore,
                penalty integer not null default 0
            );
            """
        )
        execute_db(
            self.setu_db_path,
            """
            create table if not exists setu_group_keyword
            (
                keyword  text unique on conflict ignore,
                hit      integer not null default 0,
                group_id varchar(20)
            );
            """
        )
        execute_db(
            self.setu_db_path,
            """
            create table if not exists setu_keyword
            (
                keyword text unique on conflict ignore,
                hit     integer not null default 0
            );
            """
        )
        execute_db(
            self.setu_db_path,
            """
            create table if not exists setu_keyword_replacer
            (
                original_keyword varchar(255) not null
                    constraint setu_keyword_replacer_pk primary key,
                replaced_keyword varchar(255) not null
            );
            """
        )
        execute_db(
            self.setu_db_path,
            """
            create unique index if not exists setu_keyword_replacer_original_keyword_uindex
                on setu_keyword_replacer (original_keyword);
            """
        )

    def get_setu_usage(self) -> int:
        result = execute_db(
            self.stat_db_path,
            """
            select sum(hit)
            from group_activity_count
            where tag = 'setu'
            """,
            fetch_one=True
        )

        return fetch_one_or_default(result, 0)

    def track_keyword(self, key_word: str):
        execute_db(
            self.setu_db_path,
            """
            insert or replace into setu_keyword values (?, 
                coalesce(
                    (select hit from setu_keyword where keyword = ?), 0
                ) + 1
            )
            """, (key_word, key_word)
        )

    def get_user_xp_by_keyword(self, key_word: str, user_id: Union[int, str]) -> List[Tuple[str, Union[None, str]]]:
        user_id = str(user_id)
        result = execute_db(
            self.stat_db_path,
            """
            select user_id, nickname
            from user_xp_count
            where keyword like ?
              and user_id = ?
              and nickname not null
            order by hit
            limit 5;
            """, (f'%{key_word}%', user_id),
            fetch_all=True
        )

        return result

    def _get_user_nickname(self, user_id: str) -> Optional[str]:
        result = execute_db(
            self.stat_db_path,
            """
            select nickname
            from user_activity_count
            where user_id = ?
              and nickname is not null
            limit 1;
            """, (user_id,),
            fetch_one=True
        )

        return fetch_one_or_default(result, None)

    def _get_keyword_usage_expand(self, key_word: str):
        results = execute_db(
            self.stat_db_path,
            """
            select user_id, hit
            from user_xp_count
            where keyword like ?
            order by hit desc
            limit 5;
            """, (f'%{key_word}%',),
            fetch_all=True
        )

        if not results:
            return ''

        for result in results:
            if result[0] and result[1]:
                user_id = result[0]
                nickname = self._get_user_nickname(user_id)
                if nickname is not None:
                    return f'其中，{nickname}最喜欢该XP，已经查询了{result[1]}次！！'

        return ''

    def get_keyword_usage_literal(self, key_word: str):
        setu_stat = self._get_keyword_usage(key_word)
        if setu_stat == 0:
            return '没人查过这个词呢~'

        setu_user_stat = self._get_keyword_usage_expand(key_word)
        setu_user_stat_literal = ("\n" + setu_user_stat) if setu_user_stat else ""
        return f'{key_word}被查询了{setu_stat}次~~{setu_user_stat_literal}'

    def _get_keyword_usage(self, key_word: str) -> int:
        result = execute_db(
            self.setu_db_path,
            """
            select sum(hit)
            from setu_keyword
            where keyword like ?
            """, (f'%{key_word}%',),
            fetch_one=True
        )

        return fetch_one_or_default(result, 0)

    def _keyword_filter_query(self):
        result = ['keyword != ?' for _ in self.blacklist_freq_keyword]
        return ' and '.join(result)

    def get_high_freq_keyword(self) -> List[Tuple[str]] | None:
        result = execute_db(
            self.setu_db_path,
            f"""
            select keyword, hit from setu_keyword
                where {self._keyword_filter_query()}
                order by hit desc limit 10;
            """, self.blacklist_freq_keyword,
            fetch_all=True
        )

        return result

    def get_bad_word_penalty(self, keyword: str) -> int:
        result = execute_db(
            self.setu_db_path,
            """
            select penalty
            from bad_words
            where keyword = ?
            """, (keyword,),
            fetch_one=True
        )

        return fetch_one_or_default(result, -1)

    def add_bad_word_dict(self, key_word, multiplier):
        if multiplier == 1:
            execute_db(
                self.setu_db_path,
                """
                delete
                from bad_words
                where keyword = ?
                """, (key_word,)
            )
        else:
            execute_db(
                self.setu_db_path,
                """
                insert or replace into bad_words values(?, ?)
                """, (key_word, multiplier)
            )

    def get_monitored_keywords(self) -> set:
        result = execute_db(
            self.stat_db_path,
            """
            select keyword
            from monitor_xp_data
            """,
            fetch_all=True
        )

        return set([x[0] for x in result])

    def set_new_xp(self, key_word):
        execute_db(
            self.stat_db_path,
            """
            insert or replace into monitor_xp_data (keyword, hit) values (
                ?, 0
            ) 
            """, (key_word,)
        )

    def get_xp_data(self) -> List[Tuple[str, str]]:
        result = execute_db(
            self.stat_db_path,
            """
            select keyword, hit
            from monitor_xp_data
            order by hit desc
            limit 10;
            """,
            fetch_all=True
        )

        return result

    def set_user_pixiv(self, user_id: Union[str, int], pixiv_id: Union[str, int], nickname: str) -> bool:
        if isinstance(user_id, int):
            user_id = str(user_id)

        if isinstance(pixiv_id, str):
            if not pixiv_id.isdigit():
                return False

            pixiv_id = int(pixiv_id)

        execute_db(
            self.stat_db_path,
            """
            insert or replace into user_activity_count (user_id, tag, hit, nickname) values (
                ?, ?, ?, ?
            )
            """, (user_id, 'pixiv_id', pixiv_id, nickname)
        )

        return True

    def get_user_pixiv(self, user_id) -> int:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = execute_db(
            self.stat_db_path,
            """
            select hit
            from user_activity_count
            where user_id = ?
              and tag = ?
            limit 1;
            """, (user_id, 'pixiv_id'),
            fetch_one=True
        )

        return fetch_one_or_default(result, -1)

    def _update_global_tag(self, tag: str):
        execute_db(
            self.stat_db_path,
            """
            insert or replace into global_stat (keyword, hit) values (
                ?, coalesce(
                    (select hit from global_stat where keyword = ?), 0
                ) + 1
            )
            """, (tag, tag)
        )

    def _update_user_activity(self, user_id: str, tag: str, nickname: str):
        execute_db(
            self.stat_db_path,
            """
            insert or replace into user_activity_count (user_id, tag, hit, nickname) values (
                ?, ?, coalesce(
                    (select hit from user_activity_count where user_id = ? and tag = ?), 0
                ) + 1, ?
            )
            """, (user_id, tag, user_id, tag, nickname)
        )

    def set_user_xp(self, user_id: Union[int, str], keyword: str, nickname: str):
        self.set_user_data(user_id, USER_XP, nickname, keyword)

    def set_user_data(
            self,
            user_id,
            tag: str,
            user_nickname: str,
            keyword=None,
            is_global=False
    ):
        if isinstance(user_id, int):
            user_id = str(user_id)

        if is_global:
            self._update_global_tag(tag)

        else:
            if tag != 'user_xp':
                self._update_user_activity(user_id, tag, user_nickname)
            else:
                self._update_user_xp_data(user_id, keyword, user_nickname)

    def get_global_stat(self, keyword) -> Optional[int]:
        result = execute_db(
            self.stat_db_path,
            """
            select hit
            from global_stat
            where keyword = ?
            limit 1;
            """, (keyword,),
            fetch_one=True
        )

        return fetch_one_or_default(result, None)

    def get_user_xp(self, user_id: int | str) -> List[str]:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = execute_db(
            self.stat_db_path,
            f"""
            select keyword, hit from user_xp_count where user_id = ? 
            and {self._keyword_filter_query()} order by hit desc limit 1;
            """, (user_id, *self.blacklist_freq_keyword),
            fetch_one=True
        )

        return [result[0], result[1]] if result else []

    def get_user_data_by_tag(self, user_id, tag: str):
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = execute_db(
            self.stat_db_path,
            """
            select hit
            from user_activity_count
            where user_id = ?
              and tag = ?
            limit 1;
            """, (user_id, tag),
            fetch_one=True
        )

        return fetch_one_or_default(result, 0)

    def _get_data_rank(self, user_id: str, tag: str) -> int:
        result = execute_db(
            self.stat_db_path,
            f"""
            select Rank, user_id
            from (
                  select dense_rank() over (order by hit desc) Rank, user_id from user_activity_count 
                  where tag = ?
            ) where user_id = ?
            """, (tag, user_id),
            fetch_one=True
        )

        return fetch_one_or_default(result, -1)

    def get_user_data(self, user_id: Union[int, str]) -> dict:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = execute_db(
            self.stat_db_path,
            """
            select tag, hit
            from user_activity_count
            where user_id = ?
            """, (user_id,),
            fetch_all=True
        )

        if result is None:
            return {}

        stat_dict = {}

        for r in result:
            if r[0] == 'pixiv_id':
                continue

            stat_dict[r[0]] = {}
            stat_dict[r[0]]['count'] = r[1]
            rank = self._get_data_rank(user_id, r[0])
            stat_dict[r[0]]['rank'] = rank

        return stat_dict

    def get_group_xp(self, group_id: Union[int, str]) -> List[Tuple[str]] | None:
        group_id = str(group_id)
        result = execute_db(
            self.setu_db_path,
            f"""
            select keyword, hit from setu_group_keyword where group_id = ? and {self._keyword_filter_query()}
                order by hit desc limit 5;
            """, (group_id, *self.blacklist_freq_keyword),
            fetch_all=True
        )

        return result

    def _update_group_xp(self, group_id: Union[str, int], keyword):
        group_id = str(group_id)
        execute_db(
            self.setu_db_path,
            """
            insert or replace into setu_group_keyword 
                values (?, coalesce(
                    (select hit from setu_group_keyword where keyword = ? and group_id = ?), 0
                ) + 1, ?)
            """, (keyword, keyword, group_id, group_id)
        )

    def _set_group_usage_helper(self, group_id, tag, hit=1):
        execute_db(
            self.stat_db_path,
            """
            insert or replace into group_activity_count (group_id, tag, hit) values (
                ?, ?, coalesce(
                    (select hit from group_activity_count where group_id = ? and tag = ?), 0
                ) + ?
            )
            """, (group_id, tag, group_id, tag, hit)
        )

    def set_group_xp(self, group_id, data):
        if data is None or not data:
            return

        self._update_group_xp(group_id, data)

    def set_group_data(self, group_id, tag, data=None):
        group_id = str(group_id)

        match tag:
            case 'setu' | 'yanche' | 'pull':
                self._set_group_usage_helper(group_id, tag)
            case 'pulls':
                self._set_group_usage_helper(group_id, 'pulls3', data['3'])
                self._set_group_usage_helper(group_id, 'pulls4', data['4'])
                self._set_group_usage_helper(group_id, 'pulls5', data['5'])
                self._set_group_usage_helper(group_id, 'pulls6', data['6'])

    def compare_group_activity_rank(self, tag: str, original_rank: int, hit: int) -> int:
        if original_rank <= 0:
            return original_rank

        if original_rank == 1:
            original_rank += 1
        else:
            original_rank -= 1

        result = execute_db(
            self.stat_db_path,
            """
            select *
            from (select hit,
                         rank() over (
                             partition by tag
                             order by hit desc
                             ) rank
                  from group_activity_count
                  where tag = ?)
            where rank = ?;
            """, (tag, original_rank),
            fetch_one=True
        )

        return abs(hit - result[0]) if result else -1

    def get_group_activity_rank(self, group_id: Union[int, str], tag: str) -> int:
        group_id = str(group_id)
        result = execute_db(
            self.stat_db_path,
            """
            select rank, group_id
            from (select rank() over (
                partition by tag
                order by hit desc
                ) rank,
                         group_id
                  from group_activity_count
                  where tag = ?)
            where group_id = ?
            """, (tag, group_id),
            fetch_one=True
        )

        return fetch_one_or_default(result, -1)

    def get_group_usage(self, group_id: Union[int, str], tag: str) -> int:
        group_id = str(group_id)
        result = execute_db(
            self.stat_db_path,
            """
            select hit
            from group_activity_count
            where group_id = ?
              and tag = ?
            limit 1
            """, (group_id, tag),
            fetch_one=True
        )

        return fetch_one_or_default(result, 0)

    def get_group_top_xp(self, group_id: Union[int, str]) -> str:
        group_id = str(group_id)
        query_result = execute_db(
            self.setu_db_path,
            f"""
            select keyword from setu_group_keyword 
            where group_id = ? and {self._keyword_filter_query()}
            order by hit desc limit 1;
            """, (group_id, *self.blacklist_freq_keyword),
            fetch_one=True
        )

        return fetch_one_or_default(query_result, '')

    def get_group_usage_literal(self, group_id: Union[int, str]) -> dict:
        group_id = str(group_id)
        setu_stat = self.get_group_usage(group_id, 'setu')
        yanche_stat = self.get_group_usage(group_id, 'yanche')
        freq_xp_keyword = self.get_group_top_xp(group_id)

        rank = self.get_group_activity_rank(group_id, 'setu')
        delta = self.compare_group_activity_rank('setu', rank, setu_stat)

        pulls_dict = {
            'pulls3': self.get_group_usage(group_id, 'pulls3'),
            'pulls4': self.get_group_usage(group_id, 'pulls4'),
            'pulls5': self.get_group_usage(group_id, 'pulls5'),
            'pulls6': self.get_group_usage(group_id, 'pulls6')
        }

        pulls = 0
        for _, v in pulls_dict.items():
            pulls += v

        pulls_dict['pulls'] = pulls

        return {
            'setu': setu_stat,
            'yanche': yanche_stat,
            'rank': rank,
            'delta': delta,
            'pulls': pulls_dict,
            'group_xp': freq_xp_keyword
        }

    def _update_user_xp_data(self, user_id: str, keyword: str, nickname: str):
        execute_db(
            self.stat_db_path,
            """
            insert or replace into user_xp_count (user_id, keyword, hit, nickname) values (
                ?, ?, coalesce(
                    (select hit from user_xp_count where user_id = ? and keyword = ?), 0
                ) + 1, ?
            )
            """, (user_id, keyword, user_id, keyword, nickname)
        )
