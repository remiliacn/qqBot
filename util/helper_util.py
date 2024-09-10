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
