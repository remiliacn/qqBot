from re import fullmatch
from typing import Iterable, Union, List

from nonebot.adapters.onebot.v11 import Message, MessageSegment

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'
WIKIPEDIA = 'WIKIPEDIA'


def set_group_permission(message: str, group_id: Union[str, int], tag: str) -> bool:
    from awesome.adminControl import group_control

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


MessageChainItem = Union[str, MessageSegment, Message, Iterable[MessageSegment], None]


def construct_message_chain(*args: MessageChainItem) -> Message:
    message_list: List[MessageSegment] = []

    for arg in args:
        if arg is None:
            continue

        if isinstance(arg, str):
            text = arg
            if text and not (text.endswith("\n") or fullmatch(r'[\s\r]*', text)):
                text += "\n"

            if text:
                message_list.append(MessageSegment.text(text))
            continue

        if isinstance(arg, MessageSegment):
            message_list.append(arg)
            continue

        if isinstance(arg, Message):
            message_list.extend(list(arg))
            continue

        try:
            for seg in arg:
                if isinstance(seg, MessageSegment):
                    message_list.append(seg)
        except TypeError:
            continue

    return Message(message_list)


def anime_reverse_search_response(response_data: dict) -> Message:
    similarity_raw = str(response_data.get("simlarity", ""))
    confident_prompt = ""
    try:
        similarity_val = float(similarity_raw.replace("%", ""))
    except (TypeError, ValueError):
        similarity_val = 0.0

    if similarity_val < 70:
        confident_prompt = "\n\n不过我不是太有信心哦~"

    data = response_data.get("data")

    if "est_time" in response_data:
        thumbnail = response_data.get("thumbnail")
        body = (
            f"相似度：{similarity_raw}\n"
            f"番名：{response_data.get('source', '')}\n"
            f"番剧年份：{response_data.get('year', '')}\n"
            f"集数：{response_data.get('part', '')}\n"
            f"大概出现时间：{response_data.get('est_time', '')}"
        )
        return construct_message_chain(
            MessageSegment.image(thumbnail) if thumbnail else None,
            body,
            confident_prompt,
        )

    ext_url = str(response_data.get("ext_url", ""))
    pixiv_line = "" if ext_url == "[数据删除]" else f"Pixiv：{response_data.get('pixiv_id', '')}\n"

    body = (
        f"相似度：{similarity_raw}\n"
        f"标题：{response_data.get('title', '')}\n"
        f"画师：{response_data.get('author', '')}\n"
        f"{pixiv_line}"
        f"{ext_url}"
    )

    return construct_message_chain(data, body, confident_prompt)
