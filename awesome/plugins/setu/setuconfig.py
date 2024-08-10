from typing import List

from pydantic import BaseModel


class SetuConfig(BaseModel):
    IF_REPEAT_BAN_COUNT: int = 3
    HIGH_FREQ_KEYWORDS: List[str] = [
        'white hair', 'cat ears', 'pantyhose', 'black pantyhose',
        'white pantyhose', 'arknights', 'genshin impact', 'yuri',
        'lolita', 'underclothes', 'full body', 'choker', 'masterpiece',
        'skirt', 'smile', 'collarbone', 'nurse, nurse cap', 'thighhights',
        'looking at viewer', '2girl'
    ]
