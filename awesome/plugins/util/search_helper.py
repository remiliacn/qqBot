import re

from lxml import etree

from Services.util.common_util import HttpxHelperClient


async def get_definition(
        key_word: str,
        url='https://zh.wikipedia.org/zh-cn/',
        recursive=False
):
    client = HttpxHelperClient()
    response = await client.get(f'{url}{key_word}')
    text = response.text
    e = etree.HTML(text)
    text_sections = e.xpath(
        f'//*[@id="mw-content-text"]/div[1]/p[{"1" if not recursive else "2"}]//text()'
    )
    if len(text_sections) <= 1 and not recursive:
        info_text = await get_definition(
            key_word,
            url='https://zh.wikipedia.org/wiki/',
            recursive=True
        )
    else:
        info_text = ''.join(
            [x for x in text_sections if '[' not in x and x != '\n' and 'font' not in x]
        )

        if info_text[-2:] == '：\n':
            list_entry = e.xpath('//*[@id="mw-content-text"]/div[1]/ul[1]//text()')
            if list_entry:
                info_text += ''.join([x if x != '；' else '\n' for x in list_entry])

        info_text = info_text.strip()
        info_text = re.sub(r'\[\d+]', '', info_text)
    return info_text.replace('台湾', '中国台湾').replace('中华民国', '中国台湾地区')
