HOST = '127.0.0.1'  # 必填
PORT = 5700  # 必填
SUPER_USER: int = 0  # 必填

# 群内昵称映射（可选）
NICKNAME = {}

# 机器人主人在群里的偏好称呼（可选）
SUPER_USER_PREFERRED_NAME: str = ''

# 群聊人设/系统提示词（可选，但 group_based_function 会用到）
SYSTEM_MESSAGE = ''

# Pixiv
PIXIV_REFRESH_TOKEN = ''  # 选填，用于搜图功能

# LLM / AI Keys
OPEN_API_KEY = ''  # 选填，用于 ChatGPT / OpenAI 功能
DEEPSEEK_API_KEY = ''  # 选填，用于 DeepSeek 功能
XAI_API_KEY = ''  # 选填，用于 XAI / Grok 相关功能

# DeepSeek Pricing（RMB per 1M tokens，用于估算费用）
DEEPSEEK_PRICE_INPUT_PER_1M_CACHE_HIT_RMB = 0.2
DEEPSEEK_PRICE_INPUT_PER_1M_RMB = 2.0
DEEPSEEK_PRICE_OUTPUT_PER_1M_RMB = 3.0

# Tavily Search API（联网上下文检索）
# Docs: https://docs.tavily.com/
TAVILY_API_KEY = ''

# B站 / 弹幕
DANMAKU_PROCESS = ''  # 选填，如果需要B站开播追踪功能
BILI_SESS_DATA = ''  # 选填，如果需要B站开播追踪功能

# Twitch / YouTube 下载
PATH_TO_ONEDRIVE = ''  # 选填，如果需要twitch下载功能
PATH_TEMP_DOWNLOAD = ''  # 选填，如果需要YouTube下载功能
FFMPEG_PATH = ''  # 选填，如果需要twitch或YouTube下载功能
SHARE_LINK = ''  # 选填，如果需要twitch或YouTube下载功能
CLOUD_STORAGE_SIZE_LIMIT_GB = 90

# 其他第三方
SAUCE_API_KEY = ''  # 选填，如果需要sauceNAO逆向图片搜索
DISCORD_AUTH = ''  # 选填，如果需要discord跟踪功能

# 其他会话/开关
COMMAND_START = {'/', '!', '／', '！', '#'}

# 选填：Buff cookies/session（如使用到相关功能再填）
BUFF_SESSION_ID = ''
