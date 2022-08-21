"""
Arknights headhunt recruitment simulator.
"""
import random
import sqlite3
import time
from typing import Union


class ArknightsPity:
    def __init__(self):
        self.sanity_poll_dict = {}

    def record_poll(self, group_id):
        if group_id not in self.sanity_poll_dict:
            self.sanity_poll_dict[group_id] = 10
        else:
            self.sanity_poll_dict[group_id] += 10

    def get_offset_setting(self, group_id) -> int:
        if group_id not in self.sanity_poll_dict:
            self.record_poll(group_id)
            return 0
        else:
            poll_count = self.sanity_poll_dict[group_id]
            if poll_count <= 50:
                return 0
            else:
                return (poll_count - 50) * 2

    def reset_offset(self, group_id):
        self.sanity_poll_dict[group_id] = 0


class ArkHeadhunt:
    """
    Init data for arknights headhunt simulator.
    """

    def __init__(self, times=1):
        self.times = times
        self.count = 0
        self.offset = 0
        self.arknights_agent_db = sqlite3.connect('data/db/stats.db')

        self._init()

        self.random_agent = []
        self.random_class = []

    def _init(self) -> dict:
        self.arknights_agent_db.execute(
            """
            create table if not exists arknights_op (
                "ch_name" varchar(50) unique on conflict ignore,
                "stars" integer, 
                "is_limited" boolean,
                "is_secondary_up" boolean,
                "is_up" boolean
            )
            """
        )
        self.arknights_agent_db.commit()

    def _get_if_limit_banner_on(self):
        result = self.arknights_agent_db.execute(
            """
            select ch_name from arknights_op where is_limited = true
            """
        ).fetchone()

        return result if result and result is not None else ''

    def get_randomized_results(self, offset_setting=0):
        """
        Get randomized list for agent star numbers.
        :param offset_setting: Offset that can set for rigging the result.
        :return: void.
        """
        if self.times < 0:
            raise ValueError("Pulling value cannot be less than 0")

        random.seed(time.time_ns())
        random_class = []
        self.count += 1
        for _ in range(0, self.times):
            rand_num = random.randint(0, 100) + offset_setting
            if rand_num >= 98:
                random_class.append(6)
                self.count = 0
            elif rand_num >= 90:
                random_class.append(5)
            elif rand_num >= 40:
                random_class.append(4)
            else:
                random_class.append(3)

            time.sleep(0.05)

        self.random_class = random_class
        self.random_agent = self._get_ops()

    def _get_uped_op(self, star: int):
        result = self._get_op_from_db(star, is_up=True)
        if result is None or not result:
            return self._get_op_from_db(star)

        return result

    def _get_secondary_up_op(self, star: int):
        result = self._get_op_from_db(star, is_secondary_up=True)
        if result is None:
            return self._get_op_from_db(star)

        return result

    def _get_op_count_by_stars(self, star: int) -> int:
        result = self.arknights_agent_db.execute(
            """
            select count(ch_name) from arknights_op where stars = ?
            """, (star,)
        ).fetchone()

        return int(result[0])

    def _get_op_from_db(self, star: int, is_up=False, is_secondary_up=False):
        if is_up or is_secondary_up:
            where_query = f'where stars = ? and (is_up = {is_up.__str__().lower()} ' \
                          f'or is_secondary_up = {is_secondary_up.__str__().lower()})'
        else:
            where_query = 'where stars = ?'
        result = self.arknights_agent_db.execute(
            f"""
            select ch_name from arknights_op 
            {where_query} order by random() limit 1
            """, (star,)
        ).fetchone()

        return result if result and result is not None else ''

    def _insert_op(self, star: int, name: str, is_limited=False, is_sec_up=False, is_up=False):
        is_up = is_limited or is_sec_up or is_up
        self.arknights_agent_db.execute(
            """
            insert or replace into arknights_op (ch_name, stars, is_limited, is_secondary_up, is_up) values (
                ?, ?, ?, ?, ?
            )
            """, (name, star, is_limited, is_sec_up, is_up)
        )
        self._commit_change()

    def _get_ops(self) -> list:
        """
        Get a list of agent's name.
        :return: A list with all operator names.
        """
        random_agent = []
        random.seed(time.time_ns())
        for elements in self.random_class:
            random_int = random.randint(0, 100)
            if self._get_if_limit_banner_on() and elements == 6:
                if random_int < 70:
                    random_agent.append(self._get_uped_op(6))
                else:
                    # 30%中的五倍权值爆率。
                    second_random = random.randint(0, self._get_op_count_by_stars(6))
                    if second_random < 5 and self._get_if_limit_banner_on():
                        random_agent.append(self._get_secondary_up_op(6))
                    else:
                        random_agent.append(self._get_op_from_db(6))

            else:
                if random_int < 50:
                    random_agent.append(self._get_uped_op(elements))
                else:
                    random_agent.append(self._get_op_from_db(elements))

        return random_agent

    def _get_all_secondary_up_op(self, star: int):
        result = self.arknights_agent_db.execute(
            """
            select ch_name, stars from arknights_op where stars = ? and is_secondary_up = true
            """, (star,)
        ).fetchall()

        result = [x[0] for x in result if x is not None and x[0] is not None]
        return result

    def _get_all_uped_op(self, star: int):
        result = self.arknights_agent_db.execute(
            """
            select ch_name, stars from arknights_op where stars = ? and is_up = true
            """, (star,)
        ).fetchall()

        result = [x[0] for x in result if x is not None and x[0] is not None]
        return result

    def up_op(self, agent: str, star: Union[int, str], is_limited=False, is_second_up=False, is_up=True):
        if isinstance(star, str) and not star.isdigit():
            return '?'

        star = int(star)
        self._insert_op(star, agent, is_limited, is_second_up, is_up)
        return 'Done'

    def _commit_change(self):
        self.arknights_agent_db.commit()

    def clear_ups(self):
        self.arknights_agent_db.execute(
            """
            delete from arknights_op where is_limited = true
            """
        )
        self.arknights_agent_db.execute(
            """
            update arknights_op set is_secondary_up = false, is_up = false, is_limited = false
            """
        )
        self._commit_change()

    def add_op(self, agent: str, star: Union[int, str]):
        if isinstance(star, str) and not star.isdigit():
            return '?'

        star = int(star)
        self._insert_op(star, agent)
        return f'成功将{agent}加入{star}星干员组'

    def get_up(self) -> str:
        result = ''
        four_up = self._get_all_uped_op(4)
        five_up = self._get_all_uped_op(5)
        six_up = self._get_all_uped_op(6)

        secondary_up = self._get_all_secondary_up_op(6)

        result += '四星：' + '，'.join(four_up) + '\n'
        result += '五星：' + '，'.join(five_up) + '\n'
        result += '六星：' + '，'.join(six_up) + '\n'
        result += ('六星小UP：' + '，'.join(secondary_up) + '\n') if self._get_if_limit_banner_on() else ''

        return result if result else '无\n'

    def __str__(self):
        """
        Generating the result of the headhunt.
        :return: str, the result of the headhunt in Chinese.
        """
        response = ''

        response += f'本次卡池UP：\n{self.get_up()}'
        six_star = 0
        for idx, elements in enumerate(self.random_class):
            if elements == 6 or elements == -1:
                six_star += 1

            if elements == -1:
                element = 6
            else:
                element = elements
            response += str(element) + '星干员： %s\n' % self.random_agent[idx]

        if 5 not in self.random_class and 6 not in self.random_class:
            congrats = '哈↑哈↓紫气东来'

        else:
            if six_star > 6:
                congrats = '你丫神仙吧草w'
            elif six_star > 3:
                congrats = '这个爆率感觉机器人应该是坏了吧'
            elif six_star >= 1:
                congrats = '有点幸运了啊'
            else:
                congrats = '没事这结果挺正常的，会好起来的，哈哈哈哈嗝~'

        response += '本次寻访获得了%d个六星干员，%s' % (six_star, congrats)
        return response


# Test
if __name__ == '__main__':
    api = ArkHeadhunt(times=10)
    api.get_randomized_results()
    print(api.__str__())
