from loguru import logger


def get_meme_prompt_section() -> str:
    try:
        from Services.meme_db import meme_db
        memes = meme_db.get_all_memes()
        if not memes:
            return ''

        meme_section = '\n\n【可用的表情包】\n以下是你可以使用的表情包，使用方法： <image>关键词</image>\n'
        for meme in memes:
            meme_section += f'- {meme.keyword}：（{meme.description}）\n'

        meme_section += ('\n【END OF ALL MEMES】\n'
                         '注意：只有当回复内容与表情相关且能增强表达效果时，才应该使用表情。不要生硬地加入无关表情。\n')

        return meme_section
    except Exception as err:
        logger.error(f'Failed to get meme prompt section: {err}')
        return ''
