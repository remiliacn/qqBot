from os import getcwd


class DFA:
    def __init__(self):
        self.ban_words_set = set()
        self.ban_words_list = list()
        self.ban_words_dict = dict()
        self.path = f'{getcwd()}/Services/util/filter_word.txt'
        self.get_words()

    # 获取敏感词列表
    def get_words(self):
        with open(self.path, 'r', encoding='utf-8-sig') as f:
            for s in f:
                if s.find('\\r'):
                    s = s.replace('\r', '')
                s = s.replace('\n', '')
                s = s.strip()
                if len(s) == 0:
                    continue
                if str(s) and s not in self.ban_words_set:
                    self.ban_words_set.add(s)
                    self.ban_words_list.append(str(s))
        self.add_hash_dict(self.ban_words_list)

    def change_words(self):
        self.ban_words_list.clear()
        self.ban_words_dict.clear()
        self.ban_words_set.clear()
        self.get_words()

    # 将敏感词列表转换为DFA字典序
    def add_hash_dict(self, new_list):
        for x in new_list:
            self.add_new_word(x)

    # 添加单个敏感词
    def add_new_word(self, new_word):
        new_word = str(new_word)
        # print(new_word)
        now_dict = self.ban_words_dict
        i = 0
        for x in new_word:
            if x not in now_dict:
                x = str(x)
                new_dict = dict()
                new_dict['is_end'] = False
                now_dict[x] = new_dict
                now_dict = new_dict
            else:
                now_dict = now_dict[x]
            if i == len(new_word) - 1:
                now_dict['is_end'] = True
            i += 1

    # 寻找第一次出现敏感词的位置
    def find_illegal(self, _str):
        now_dict = self.ban_words_dict
        i = 0
        start_word = -1
        is_start = True  # 判断是否是一个敏感词的开始
        while i < len(_str):
            if _str[i] not in now_dict:
                if is_start is True:
                    i += 1
                    continue
                i = start_word + 1
                start_word = -1
                is_start = True
                now_dict = self.ban_words_dict
            else:
                if is_start is True:
                    start_word = i
                    is_start = False
                now_dict = now_dict[_str[i]]
                if now_dict['is_end'] is True:
                    return start_word
                else:
                    i += 1
        return -1

    # 查找是否存在敏感词
    def exists(self, s: str):
        pos = self.find_illegal(s.lower())
        if pos == -1:
            return False
        else:
            return True
