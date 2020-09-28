import json
import re
import os

import requests
from aiocqhttp import MessageSegment
from googletrans import Translator
from nonebot.log import logger

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'

def get_downloaded_image_path(response: dict, path: str):
    url = response['url']
    image_response = requests.get(
        url,
        stream=True
    )
    image_response.raise_for_status()
    path = f'{path}/{response["filename"]}'
    if not os.path.exists(path):
        with open(path, 'wb') as file:
            file.write(image_response.content)

    resp = str(MessageSegment.image(f'file:///{path}'))
    return resp

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


def ark_helper(args: list) -> str:
    if len(args) != 2:
        return '用法有误\n' + '使用方法：！命令 干员名 星级（数字）'

    if not args[1].isdigit():
        return '使用方法有误，第二参数应为数字'

    return ''

def send_message_with_mini_program(title: str, content: list, image=None, action: list=None) -> str:
    data = {
      "app": "com.tencent.miniapp",
      "desc": "",
      "view": "notification",
      "ver": "1.0.0.11",
      "prompt": "[又有lsp在搜图]",
      "appID": "",
      "sourceName": "",
      "actionData": "",
      "actionData_A": "",
      "sourceUrl": "",
      "meta": {
        "notification": {
          "appInfo": {
            "appName": "",
            "appType": 4,
            "appid": 1109659848,
            "iconUrl": image if image is not None else ""
          },
          "data": content,
          "title": title,
          "button": action if action is not None else [],
          "emphasis_keyword": ""
        }
      },
      "text": "",
      "sourceAd": ""
    }

    result = json.dumps(data)
    result = result.replace('&', '&amp;').replace(',', '&#44;').replace('[', '&#91;').replace(']', '&#93;')
    return f'[CQ:json,data={result}]'
