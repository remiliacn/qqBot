import re

from googletrans import Translator
from nonebot.log import logger

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'


class HhshCache:
    def __init__(self):
        self.meaning_dict = {}  # str : str
        self.furigana_dict = {}

    def check_exist(self, query, function):
        if function == HHSHMEANING:
            return query in self.meaning_dict

        if function == FURIGANAFUNCTION:
            return query in self.furigana_dict

    def store_result(self, query: str, meaning: str, function: (HHSHMEANING or FURIGANAFUNCTION)):
        if function == HHSHMEANING:
            if len(self.meaning_dict) > 100:
                first_key = next(iter(self.meaning_dict))
                del self.meaning_dict[first_key]

            self.meaning_dict[query] = meaning

        elif function == FURIGANAFUNCTION:
            if len(self.furigana_dict) > 100:
                first_key = next(iter(self.furigana_dict))
                del self.furigana_dict[first_key]

            self.furigana_dict[query] = meaning

    def get_result(self, query, function):
        if function == HHSHMEANING:
            return self.meaning_dict[query]

        if function == FURIGANAFUNCTION:
            return self.furigana_dict[query]


class translation:
    def __init__(self):
        self.dest = 'zh-cn'
        self.announc = False
        self.INFO_NOT_AVAILABLE = '翻译出错了呢'

    def getTranslationResult(self, sentence):
        sentence = str(sentence)
        syntax = re.compile('\[CQ.*?\]')
        sentence = re.sub(syntax, '', sentence)
        translator = Translator()

        try:
            if translator.detect(text=sentence).lang != 'zh-CN' and translator.detect(text=sentence).lang != 'zh-TW':
                result = translator.translate(text=sentence, dest='zh-cn').text
            else:
                result = '英文翻译：' + translator.translate(text=sentence, dest='en').text + '\n' \
                         + '日文翻译：' + translator.translate(text=sentence, dest='ja').text

            return result

        except Exception as e:
            logger.warning('Something went wrong when trying to translate %s' % e)
            return self.INFO_NOT_AVAILABLE
