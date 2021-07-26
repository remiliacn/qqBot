"""
Arknights headhunt recruitment simulator.
"""

import random
import time
from json import loads, dump
from os.path import exists
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
            pollCount = self.sanity_poll_dict[group_id]
            if pollCount <= 50:
                return 0
            else:
                return (pollCount - 50) * 2

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
        self.agent_dict = self._get_agent_dict()
        self.random_agent = []
        self.random_class = []

    @staticmethod
    def _get_agent_dict() -> dict:
        if not exists('Services/util/agent.json'):
            with open('Services/util/agent.json', 'w+', encoding='utf8') as file:
                dump({}, file, indent=4)

        with open('Services/util/agent.json', 'r', encoding='utf8') as file:
            agent_dict = loads(file.read())

        return agent_dict

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

    def _get_ops(self) -> list:
        """
        Get a list of agent's name.
        :return: A list with all operator names.
        """
        random_agent = []
        random.seed(time.time_ns())
        for elements in self.random_class:
            random_int = random.randint(0, 100)
            if self.agent_dict['limited'] and elements == 6:
                if random_int < 70:
                    random_agent.append(random.choice(self.agent_dict[f'UP6']))
                else:
                    # 30%中的五倍权值爆率。
                    second_random = random.randint(0, len(self.agent_dict['6']))
                    if second_random < 5 and 'sixSecondaryUp' in self.agent_dict and self.agent_dict['sixSecondaryUp']:
                        random_agent.append(random.choice(self.agent_dict['sixSecondaryUp']))
                    else:
                        random_agent.append(random.choice(self.agent_dict['6']))

            else:
                if random_int < 50 and self.agent_dict[f'UP{elements}']:
                    random_agent.append(random.choice(self.agent_dict[f'UP{elements}']))
                else:
                    random_agent.append(random.choice(self.agent_dict[str(elements)]))

        return random_agent

    def set_if_banner_limited(self, setting=False):
        self.agent_dict['limited'] = setting
        self.update_content()

    def set_up(self, agent: str, star: Union[int, str], is_second_up=False):
        if isinstance(star, int):
            star = str(star)

        if agent in self.agent_dict[star]:
            if agent not in self.agent_dict[f'UP{star}']:
                if not is_second_up:
                    self.agent_dict[f'UP{star}'].append(agent)
                else:
                    self.agent_dict['sixSecondaryUp'] = []
                    self.agent_dict['sixSecondaryUp'].append(agent)

                self.update_content()
                return 'Done'

            return f'干员{agent}已被UP'

        return f'干员{agent}不是{star}星或不在游戏内。'

    def update_content(self):
        with open('Services/util/agent.json', 'w+', encoding='utf8') as file:
            dump(self.agent_dict, file, indent=4, ensure_ascii=False)

    def clear_ups(self):
        self.agent_dict['UP3'] = []
        self.agent_dict['UP4'] = []
        self.agent_dict['UP5'] = []
        self.agent_dict['UP6'] = []

        self.agent_dict['limited'] = False

        if 'sixSecondaryUp' in self.agent_dict:
            self.agent_dict['sixSecondaryUp'] = []

        self.update_content()

    def add_op(self, agent: str, star: Union[int, str]):
        if isinstance(star, int):
            star = str(star)

        if agent not in self.agent_dict[star]:
            self.agent_dict[star].append(agent)
            self.update_content()
            return f'成功将{agent}加入{star}星干员组'

        return f'{agent}已存在与{star}星干员组'

    def get_up(self) -> str:
        result = ''
        four_up = self.agent_dict['UP4']
        five_up = self.agent_dict['UP5']
        six_up = self.agent_dict['UP6']
        if 'sixSecondaryUp' in self.agent_dict and self.agent_dict['sixSecondaryUp']:
            secondary_up = self.agent_dict['sixSecondaryUp']
        else:
            secondary_up = ''

        if four_up:
            result += '四星：'
            result += '，'.join(map(str, four_up))
            result += '\n'

        if five_up:
            result += '五星：'
            result += '，'.join(map(str, five_up))
            result += '\n'

        if six_up:
            result += '六星：'
            result += '，'.join(map(str, six_up))
            result += '\n'

        if secondary_up:
            result += '六星保底UP：'
            result += '，'.join(map(str, secondary_up))
            result += '\n'

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
    print(api.set_up('W', 6))
    api.get_randomized_results(offset_setting=98)
    print(api.__str__())
