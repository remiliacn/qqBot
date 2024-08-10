from os import getcwd

CHITCHAT_PIC_TYPES = ('恰柠檬', '流泪猫猫头', '迫害', '辛苦了', '不愧是你', '威胁', '社保', '恰桃')
CHITCHAT_PIC_DICT = {
    '恰柠檬': f'{getcwd()}/data/dl/lemon/',
    '流泪猫猫头': f'{getcwd()}/data/dl/useless/',
    '迫害': f'{getcwd()}/data/dl/pohai/',
    '辛苦了': f'{getcwd()}/data/dl/otsukare/',
    '不愧是你': f'{getcwd()}/data/dl/bukui/',
    '威胁': f'{getcwd()}/data/dl/weixie/',
    '社保': f'{getcwd()}/data/dl/shebao/',
    '恰桃': f'{getcwd()}/data/dl/peach/',
}

NEEDS_THINGS_TO_ADD_PROMPT = '要加什么进来呢？'
NEEDS_QQ_NUMBER_PROMPT = '请输入一个qq号'
PROMPT_FOR_KEYWORD = '请输入一个关键词！'
NEEDS_QUESTION_PROMPT = '啊？你要问我什么？'
ADD_PIC_PROMPT = f'请输入要加入的类型，类型应该为这其中的一个：{CHITCHAT_PIC_TYPES}\n' \
                 f'然后添加一个空格再加上需要添加的图'
