import sqlite3
from sqlite3 import Cursor
from typing import Union, List, Tuple


class SetuFunction:
    def __init__(self):
        self.max_sanity = 100
        self.blacklist_freq_keyword = ('R-18', 'オリジナル')
        self.sanity_dict = {}
        self.happy_hours = False
        self.remind_dict = {}
        self.ordered_stat = {}

        self.setu_db_path = 'data/db/setu.db'
        self.stat_db_path = 'data/db/stats.db'
        self.setu_db_connection = sqlite3.connect(self.setu_db_path)
        self.stat_db_connection = sqlite3.connect(self.stat_db_path)

    def get_setu_usage(self) -> int:
        result = self.stat_db_connection.execute(
            """
            select sum(hit) from group_activity_count where tag = 'setu'
            """
        ).fetchone()

        return result[0] if result is not None and result[0] is not None else 0

    def track_keyword(self, key_word):
        self.setu_db_connection.execute(
            """
            insert or replace into setu_keyword values (?, 
                coalesce(
                    (select hit from setu_keyword where keyword = ?), 0
                ) + 1
            )
            """, (key_word, key_word)
        )
        self.commit_change()

    def get_user_xp_by_keyword(self, key_word: str, user_id: Union[int, str]) -> List[Tuple[str, Union[None, str]]]:
        user_id = str(user_id)
        result = self.stat_db_connection.execute(
            """
            select user_id, nickname from user_xp_count 
            where keyword like ? and user_id = ? and nickname not null order by hit limit 5;
            """, (f'%{key_word}%', user_id)
        ).fetchall()

        return result

    def _get_keyword_usage_expand(self, key_word: str):
        result = self.stat_db_connection.execute(
            """
            select nickname, hit from user_xp_count 
            where keyword like ? and nickname is not null 
            order by hit desc limit 1;
            """, (f'%{key_word}%',)
        ).fetchone()

        if result is not None and result[0] is not None and result[1] is not None:
            return f'其中，{result[0]}最喜欢该XP，已经查询了{result[1]}次！！'

        return ''

    def get_keyword_usage_literal(self, key_word: str):
        setu_stat = self._get_keyword_usage(key_word)
        if setu_stat == 0:
            return '没人查过这个词呢~'

        setu_user_stat = self._get_keyword_usage_expand(key_word)
        setu_user_stat_literal = ("\n" + setu_user_stat) if setu_user_stat else ""
        return f'{key_word}被查询了{setu_stat}次~~{setu_user_stat_literal}'

    def _get_keyword_usage(self, key_word: str) -> int:
        result = self.setu_db_connection.execute(
            """
            select sum(hit) from setu_keyword where keyword like ?
            """, (f'%{key_word}%',)
        ).fetchone()

        return result[0] if result is not None and result[0] is not None else 0

    def get_high_freq_keyword(self) -> Cursor:
        result = self.setu_db_connection.execute(
            """
            select keyword, hit from setu_keyword
                where keyword != ? and keyword != ?
                order by hit desc limit 10;
            """, self.blacklist_freq_keyword
        ).fetchall()

        return result

    def get_max_sanity(self) -> int:
        return self.max_sanity

    def get_bad_word_penalty(self, keyword: str) -> int:
        result = self.setu_db_connection.execute(
            """
            select penalty from bad_words where keyword = ?
            """, (keyword,)
        ).fetchone()

        return result[0] if result is not None else 1

    def add_bad_word_dict(self, key_word, multiplier):
        if multiplier == 1:
            self.setu_db_connection.execute(
                """
                delete from bad_words where keyword = ?
                """, (key_word,)
            )
        else:
            self.setu_db_connection.execute(
                """
                insert or replace into bad_words values(?, ?)
                """, (key_word, multiplier)
            )

        self.commit_change()

    def get_monitored_keywords(self) -> set:
        result = self.stat_db_connection.execute(
            """
            select keyword from monitor_xp_data
            """
        ).fetchall()

        return set([x[0] for x in result])

    def set_new_xp(self, key_word):
        self.stat_db_connection.execute(
            """
            insert or replace into monitor_xp_data (keyword, hit) values (
                ?, 0
            ) 
            """, (key_word,)
        )
        self.commit_change()

    def get_xp_data(self) -> List[Tuple[str, str]]:
        result = self.stat_db_connection.execute(
            """
            select keyword, hit from monitor_xp_data order by hit desc limit 10;
            """
        ).fetchall()

        return result

    def set_user_pixiv(self, user_id, pixiv_id) -> bool:
        if isinstance(user_id, int):
            user_id = str(user_id)

        if isinstance(pixiv_id, str):
            if not pixiv_id.isdigit():
                return False

            pixiv_id = int(pixiv_id)

        self.stat_db_connection.execute(
            """
            insert or replace into user_activity_count (user_id, tag, hit) values (
                ?, ?, ?
            )
            """, (user_id, 'pixiv_id', pixiv_id)
        )

        self.commit_change()
        return True

    def get_user_pixiv(self, user_id) -> int:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = self.stat_db_connection.execute(
            """
            select hit from user_activity_count where user_id = ? and tag = ? limit 1;
            """, (user_id, 'pixiv_id')
        ).fetchone()

        return result[0] if result is not None else -1

    def _update_global_tag(self, tag: str):
        self.stat_db_connection.execute(
            """
            insert or replace into global_stat (keyword, hit) values (
                ?, coalesce(
                    (select hit from global_stat where keyword = ?), 0
                ) + 1
            )
            """, (tag, tag)
        )
        self.commit_change()

    def _update_user_activity(self, user_id: str, tag: str, nickname: str):
        self.stat_db_connection.execute(
            """
            insert or replace into user_activity_count (user_id, tag, hit, nickname) values (
                ?, ?, coalesce(
                    (select hit from user_activity_count where user_id = ? and tag = ?), 0
                ) + 1, ?
            )
            """, (user_id, tag, user_id, tag, nickname)
        )
        self.commit_change()

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

    def get_global_stat(self) -> List[Tuple[str, int]]:
        result = self.stat_db_connection.execute(
            """
            select keyword, hit from global_stat
            """
        ).fetchall()

        return result

    def get_user_xp(self, user_id) -> Union[List[Tuple[str, int]], str]:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = self.stat_db_connection.execute(
            """
            select keyword from user_xp_count where user_id = ? 
            and keyword != ? and keyword != ? order by hit desc limit 1;
            """, (user_id, *self.blacklist_freq_keyword)
        ).fetchone()

        return result[0] if result is not None else '暂无数据'

    def get_user_data_by_tag(self, user_id, tag: str):
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = self.stat_db_connection.execute(
            """
            select hit from user_activity_count where user_id = ? and tag = ? limit 1;
            """, (user_id, tag)
        ).fetchone()

        return result[0] if result is not None else 0

    def _get_data_rank(self, user_id: str, tag: str) -> int:
        result = self.stat_db_connection.execute(
            f"""
            select Rank, user_id
            from (
                  select rank() over (order by hit desc) Rank, user_id from user_activity_count 
                  where tag = ?
            ) where user_id = ?
            """, (tag, user_id)
        ).fetchone()

        return result[0] if result is not None and result[0] is not None else -1

    def get_user_data(self, user_id: Union[int, str]) -> dict:
        if isinstance(user_id, int):
            user_id = str(user_id)

        result = self.stat_db_connection.execute(
            """
            select tag, hit
            from user_activity_count where user_id = ?
            """, (user_id,)
        ).fetchall()

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

    def get_sanity_dict(self):
        return self.sanity_dict

    def get_group_xp(self, group_id) -> Cursor:
        group_id = str(group_id)
        result = self.setu_db_connection.execute(
            """
            select keyword, hit from setu_group_keyword where group_id = ?
                order by hit desc limit 5;
            """, (group_id,)
        ).fetchall()
        return result

    def update_group_xp(self, group_id: Union[str, int], keyword):
        group_id = str(group_id)
        self.setu_db_connection.execute(
            """
            insert or replace into setu_group_keyword 
                values (?, coalesce(
                    (select hit from setu_group_keyword where keyword = ? and group_id = ?), 0
                ) + 1, ?)
            """, (keyword, keyword, group_id, group_id)
        )
        self.setu_db_connection.commit()

    def _set_group_usage_helper(self, group_id, tag, hit=1):
        self.stat_db_connection.execute(
            """
            insert or replace into group_activity_count (group_id, tag, hit) values (
                ?, ?, coalesce(
                    (select hit from group_activity_count where group_id = ? and tag = ?), 0
                ) + ?
            )
            """, (group_id, tag, group_id, tag, hit)
        )

    def set_group_usage(self, group_id, tag, data=None):
        group_id = str(group_id)

        if tag == 'setu' or tag == 'yanche' or tag == 'pull':
            self._set_group_usage_helper(group_id, tag)

        elif tag == 'groupXP':
            if data is None:
                return

            self.update_group_xp(group_id, data)

        elif tag == 'pulls':
            self._set_group_usage_helper(group_id, 'pulls3', data['3'])
            self._set_group_usage_helper(group_id, 'pulls4', data['4'])
            self._set_group_usage_helper(group_id, 'pulls5', data['5'])
            self._set_group_usage_helper(group_id, 'pulls6', data['6'])

        self.commit_change()

    def compare_group_activity_rank(self, tag: str, original_rank: int, hit: int) -> int:
        if original_rank <= 0:
            return original_rank

        if original_rank == 1:
            original_rank += 1
        else:
            original_rank -= 1

        result = self.stat_db_connection.execute(
            """
            select * from (
                select hit, rank () over ( 
                        partition by tag
                        order by hit desc
                ) rank from group_activity_count where tag = ?
            ) where rank = ?;
            """, (tag, original_rank)
        ).fetchone()

        return abs(hit - result[0]) if result is not None else -1

    def get_group_activity_rank(self, group_id: Union[int, str], tag: str) -> int:
        group_id = str(group_id)
        result = self.stat_db_connection.execute(
            """
            select rank() over(order by hit desc) 
            from group_activity_count where group_id = ? and tag = ?
            """, (group_id, tag)
        ).fetchone()

        return result[0] if result is not None else -1

    def get_group_usage(self, group_id: Union[int, str], tag: str) -> int:
        group_id = str(group_id)
        result = self.stat_db_connection.execute(
            """
            select hit from group_activity_count where group_id = ? and tag = ? limit 1
            """, (group_id, tag)
        ).fetchone()

        return result[0] if result is not None else 0

    def get_group_usage_literal(self, group_id) -> dict:
        group_id = str(group_id)
        setu_stat = self.get_group_usage(group_id, 'setu')
        yanche_stat = self.get_group_usage(group_id, 'yanche')

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
            'pulls': pulls_dict
        }

    def set_remind_dict(self, group_id, stats):
        self.remind_dict[group_id] = stats

    def set_sanity(self, group_id, sanity=2000):
        self.sanity_dict[group_id] = sanity

    def drain_sanity(self, group_id, sanity=1):
        self.sanity_dict[group_id] -= sanity

    def get_sanity(self, group_id):
        return self.sanity_dict[group_id]

    def fill_sanity(self, group_id=None, sanity=1):
        if group_id is None:
            for elements in self.sanity_dict:
                if self.sanity_dict[elements] + sanity > 0:
                    self.remind_dict[elements] = False
                if self.happy_hours:
                    if not self.sanity_dict[elements] >= self.max_sanity * 2:
                        self.sanity_dict[elements] += sanity
                else:
                    if not self.sanity_dict[elements] >= self.max_sanity:
                        self.sanity_dict[elements] += sanity
        else:
            if self.sanity_dict[group_id] + sanity > 0:
                self.remind_dict[group_id] = False
            self.sanity_dict[group_id] += sanity

    def commit_change(self):
        self.stat_db_connection.commit()
        self.setu_db_connection.commit()

    def _update_user_xp_data(self, user_id: str, keyword: str, nickname: str):
        self.stat_db_connection.execute(
            """
            insert or replace into user_xp_count (user_id, keyword, hit, nickname) values (
                ?, ?, coalesce(
                    (select hit from user_xp_count where user_id = ? and keyword = ?), 0
                ) + 1, ?
            )
            """, (user_id, keyword, user_id, keyword, nickname)
        )
        self.commit_change()
