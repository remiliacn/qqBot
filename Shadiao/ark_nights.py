"""
Arknights headhunt recruitment simulator.
"""

import random
import time

AGENT6 = ['能天使', '推进之王', '伊芙利特', '艾雅法拉', '安洁莉娜',
          '闪灵', '夜莺', '星熊', '塞雷娅', '银灰', '斯卡蒂', '风笛',
          '早露', '赫拉格', '傀影', '煌', '阿', '陈', '麦哲伦', '莫斯提马', '黑',
          '温蒂', 'W', '铃兰']

AGENT5 = ['白面鸮', '凛冬', '德克萨斯', '芙兰卡', '拉普兰德', '幽灵鲨', '蓝毒',
          '白金', '陨星', '天火', '梅尔', '赫默', '华法琳', '临光',
          '红', '雷蛇', '可颂', '普罗旺斯', '守林人', '崖心', '初雪',
          '真理', '空', '狮蝎', '食铁兽', '夜魔', '惊蛰', '哞', '巫恋',
          '极境', '月禾', '莱恩哈特', '布洛卡', '灰喉', '石棉', '苇草',
          '送葬人', '星极', '诗怀雅', '格劳克斯', '槐琥', '慑砂']

AGENT4 = ['夜烟', '远山', '杰西卡', '流星', '白雪', '清道夫', '红豆',
          '杜宾', '缠丸', '霜叶', '慕斯', '砾', '暗锁', '末药',
          '调香师', '角峰', '蛇屠箱', '古米', '深海色', '地灵', '阿消',
          '猎蜂', '格雷伊', '苏苏洛', '桃金娘', '红云', '梅', '安比尔',
          '宴', '刻刀', '波登可']

AGENT3 = ['芬', '香草', '翎羽', '玫兰莎', '卡缇', '米格鲁', '克洛丝',
          '炎熔', '芙蓉', '安塞尔', '史都华德', '梓兰', '月见夜', '空爆', '斑点', '泡普卡']

AGENT_DICT = {
    3 : AGENT3,
    4 : AGENT4,
    5 : AGENT5,
    6 : AGENT6
}

class ArkHeadhunt:
    """
    Init data for arknights headhunt simulator.
    """
    def __init__(self, times=1):
        self.times = times
        self.count = 0
        self.offset = 0
        self.random_agent = []
        self.random_class = []

    def get_randomized_results(self, offset_setting: int):
        """
        Get randomized list for agent star numbers.
        :param offset_setting: Offset that can set for rigging the result.
        :return: void.
        """
        if self.times < 0:
            raise ValueError("Pulling value cannot be less than 0")

        self.random_agent.clear()
        self.random_class.clear()
        random.seed(time.time_ns())
        random_class = []
        self.count += 1
        for _ in range(0, self.times):
            rand_num = random.randint(1, 101) + offset_setting
            if rand_num > 98:
                random_class.append(6)
                self.count = 0
            elif rand_num > 90:
                random_class.append(5)
            elif rand_num > 40:
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
            agent_list = AGENT_DICT[elements]
            agent_idx = random.randint(0, len(agent_list) - 1)
            random_agent.append(agent_list[agent_idx])

        return random_agent

    def __str__(self):
        """
        Generating the result of the headhunt.
        :return: str, the result of the headhunt in Chinese.
        """
        response = ''
        response += '您抽到的东西有~蹡蹡！\n'
        six_star = 0
        for idx, elements in enumerate(self.random_class):
            if elements == 6:
                six_star += 1
            response += str(elements) + '星干员： %s\n' % self.random_agent[idx]


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
