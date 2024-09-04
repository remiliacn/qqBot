import json
from typing import Union, List

from nonebot.adapters.onebot.v11 import Message, MessageSegment

from awesome.adminControl import group_control

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'
WIKIPEDIA = 'WIKIPEDIA'


def set_group_permission(message: str, group_id: Union[str, int], tag: str) -> bool:
    group_id = str(group_id)
    if '开' in message:
        group_control.set_group_permission(group_id=group_id, tag=tag, stat=True)
        return True

    group_control.set_group_permission(group_id=group_id, tag=tag, stat=False)
    return False


def ark_helper(args: list) -> str:
    if len(args) < 2:
        return '用法有误\n' + '使用方法：！命令 干员名 星级（数字）'

    if not args[1].isdigit():
        return '使用方法有误，第二参数应为数字'

    return ''


def construct_message_chain(*args: [str, MessageSegment, Message, List[MessageSegment], None]) -> Message:
    message_list: List[MessageSegment] = []
    for arg in args:
        if arg is None:
            continue

        if isinstance(arg, str):
            if arg:
                message_list.append(MessageSegment.text(arg))
        elif isinstance(arg, Message):
            message_list += [x for x in arg]
        elif isinstance(arg, list):
            message_list += arg
        else:
            message_list.append(arg)

    return Message(message_list)


@DeprecationWarning
def send_message_with_mini_program(title: str, content: list, image=None, action: list = None) -> str:
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


def anime_reverse_search_response(response_data: dict) -> Message:
    confident_prompt = ''
    if 'simlarity' in response_data and float(response_data["simlarity"].replace('%', '')) < 70:
        confident_prompt = '\n\n不过我不是太有信心哦~'
    if 'est_time' in response_data:
        response = construct_message_chain(MessageSegment.image(response_data["thumbnail"]),
                                           f'相似度：{response_data["simlarity"]}\n'
                                           f'番名：{response_data["source"]}\n'
                                           f'番剧年份：{response_data["year"]}\n'
                                           f'集数：{response_data["part"]}\n'
                                           f'大概出现时间：{response_data["est_time"]}', confident_prompt)
    else:
        if response_data['ext_url'] == '[数据删除]':
            response = construct_message_chain(response_data['data'],
                                               f'相似度：{response_data["simlarity"]}\n'
                                               f'标题：{response_data["title"]}\n'
                                               f'画师：{response_data["author"]}\n'
                                               f'{str(response_data["ext_url"])}', confident_prompt)
        else:
            response = construct_message_chain(response_data['data'],
                                               f'相似度：{response_data["simlarity"]}\n'
                                               f'标题：{response_data["title"]}\n'
                                               f'画师：{response_data["author"]}\n'
                                               f'Pixiv：{response_data["pixiv_id"]}\n'
                                               f'{str(response_data["ext_url"])}', confident_prompt)

    return response


@DeprecationWarning
def send_as_xml_message(
        brief: str, title: str, summary: str,
        url: str = None, image: str = None,
        source: str = None
):
    message = f"""
    <?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <msg 
        serviceID="146" templateID="1" action="web" 
        brief="{brief}" sourceMsgId="0" url="{url if url is not None else 'https://www.example.com'}" 
        flag="0" adverSign="0" multiMsgFlag="0"
    >
        <item layout="2" advertiser_id="0" aid="0">
            <picture cover="{image if image is not None else ''}" />
            <title>{title}</title>
            <summary>{summary}</summary>
        </item>
        <source 
            name="{source if source is not None else '官方认证消息'}" 
            icon="https://qzs.qq.com/ac/qzone_v5/client/auth_icon.png" action="" appid="-1" 
        />
    </msg>
    """
    return f'[CQ:xml,data={message}]'
