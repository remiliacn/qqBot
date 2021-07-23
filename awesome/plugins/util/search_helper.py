import aiohttp
from lxml import etree


async def get_definition(
        key_word: str,
        url='https://zh.wikipedia.org/zh-cn/',
        recursive=False
):
    async with aiohttp.ClientSession() as session:
        async with session.get(
                f'{url}{key_word}'
        ) as response:
            text = await response.text()
            e = etree.HTML(text)
            text_sections = e.xpath(
                f'//*[@id="mw-content-text"]/div[1]/p[{"1" if not recursive else "2"}]//text()'
            )
            if len(text_sections) <= 1 and not recursive:
                return await get_definition(
                    key_word,
                    url='https://zh.wikipedia.org/wiki/',
                    recursive=True
                )

            info_text = ''.join(
                [x for x in text_sections if '[' not in x and x != '\n' and 'font' not in x]
            )

            if '可以指' in info_text:
                list_entry = e.xpath('//*[@id="mw-content-text"]/div[1]/ul/li//text()')
                info_text += ''.join([x if x != '；' else '\n' for x in list_entry])
                print()
            return info_text.strip()
