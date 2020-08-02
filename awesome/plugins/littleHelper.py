import nonebot, requests, json, time, logging, re
from Shadiao import randomServices
from googletrans import Translator
from youdaoService import youdao
from Shadiao import Shadiao
from awesome.plugins.Shadiao import sanity_meter

from awesome.adminControl import userControl

answer_api = userControl.Grouplearning()

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'

class LittleHelper:
    def __init__(self, limit=20):
        self.source_dict = {
             708157568 : 'http://s3.wyxxzt.cn/api/hanayori.json?op=list&limit=%d' % limit
        }
        self.CONNECTION_ERROR = '连接错误！'
        self.PERMISSION_ERROR = '您无权限查看源'
        self.KEY_ERROR = '序号错误'
        self.INFO_NOT_AVAILABLE = '未查到您所查询的信息'
        self.url_list = []

    def get_names_from_group(self, group_id):
        name = ''
        url_list = []
        if group_id in self.source_dict:
            page = requests.get(self.source_dict[group_id], timeout=10).content.decode('utf-8')
            json_data = json.loads(page)
            if json_data['code'] == 200:
                for idx, elements in enumerate(json_data['data']):
                    name += str(idx + 1) + '、' + elements['name'] + '\n'
                    url_list.append(elements['url'])

            else:
                name = self.CONNECTION_ERROR

        else:
            name = self.PERMISSION_ERROR

        self.url_list = url_list
        return name

    def get_url_from_index(self, index):
        try:
            if int(index) <= 0:
                return self.KEY_ERROR
            index = int(index) - 1
        except ValueError:
            return self.KEY_ERROR

        if len(self.url_list) != 0 and index < len(self.url_list):
            return self.url_list[index]

        return self.INFO_NOT_AVAILABLE

class HhshCache:
    def __init__(self):
        self.meaning_dict = {}       # str : str
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

helper = LittleHelper()
translator = Translator()
cache = HhshCache()

class translation:
    def __init__(self):
        self.dest = 'zh-cn'
        self.announc = False
        self.INFO_NOT_AVAILABLE = '翻译出错了呢'

    def getTranslationResult(self, sentence):
        sentence = str(sentence)
        syntax = re.compile('\[CQ.*?\]')
        sentence = re.sub(syntax, '', sentence)

        try:
            if translator.detect(text=sentence).lang != 'zh-CN' and translator.detect(text=sentence).lang != 'zh-TW':
                result = translator.translate(text=sentence, dest='zh-cn').text
            else:
                result = '英文翻译：' + translator.translate(text=sentence, dest='en').text + '\n' \
                            +'日文翻译：' + translator.translate(text=sentence, dest='ja').text

            return result

        except Exception as e:
            logging.warning('Something went wrong when trying to translate %s' % e)
            return self.INFO_NOT_AVAILABLE

@nonebot.on_command('help', only_to_me=False)
async def send_help(session: nonebot.CommandSession):
    await session.send('请移步\n'
                       'https://github.com/remiliacn/Lingye-Bot/blob/master/README.md\n'
                       '如果有新功能想要添加，请提交issue!')

@nonebot.on_command('翻译', only_to_me=False)
async def translate(session : nonebot.CommandSession):
    trans = translation()
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    sentence = session.get('content', prompt='翻译的内容呢？')
    try:
        get_result = trans.getTranslationResult(sentence=sentence)
    except Exception as e:
        logging.warning('翻译出错！%s' % e)
        await session.send('翻译出错了！请重试！')
        return

    await session.send('以下来自于谷歌翻译的结果，仅供参考：\n%s' % get_result)

@translate.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['content'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('你这是想让我翻译什么啊kora')

    session.state[session.current_key] = stripped_arg

@nonebot.on_command('日语词典', only_to_me=False)
async def getYouDaoService(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    key_word = session.get('key_word', prompt='词呢！词呢！！KORA！！！')
    if key_word != '':
        you = youdao.Youdaodict(keyWord=key_word)
        await session.send('以下是%s的查询结果\n%s' % (key_word, you.explain_to_string()))

    else:
        await session.send('...')

@nonebot.on_command('最新地震', only_to_me=False)
async def send_earth_quake_info(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    earth_quake_api_new = randomServices.Earthquakeinfo()
    new_earthquake_info = earth_quake_api_new.get_newest_info()
    await session.send(new_earthquake_info)

@nonebot.on_command('日日释义', only_to_me=False)
async def jpToJpDict(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    key_word = session.get('key_word', prompt='请输入一个关键字！')
    goo_api = None
    try:
        goo_api = youdao.Goodict(keyWord=key_word)
    except Exception as e:
        logging.warning('something went wrong in jptojpdict %s' % e)
        await session.finish('悲！连接出错惹')

    result, okay_or_not = goo_api.get_title_string()
    if okay_or_not:
        number = session.get('number', prompt='%s\n请输入要查询的部分的序号！' % result)
        try:
            number = int(number)
        except ValueError:
            await session.send('序号出错！')
            return

        goo_api.get_list(index=number)
        result = goo_api.get_explaination()
        await session.send('你查询的关键字%s的结果如下：\n%s' % (key_word, result))

    else:
        await session.send('出大错惹！！尝试新算法中……')
        goo_api.get_list(index=0, page='exception')
        result = goo_api.get_explaination()
        await session.send('你查询的关键字%s的结果如下：\n%s' % (key_word, result))

@nonebot.on_command('释义nico', only_to_me=False)
async def nico_send(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    keyWord = session.get('keyWord', prompt='歪？我的关键字呢？')
    api = youdao.Nicowiki(keyWord=keyWord)
    await session.send(api.__str__())
    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'nico')

@nonebot.on_command('周公解梦', only_to_me=False)
async def zhou_interprets(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if answer_api.get_if_user_banned(ctx['user_id']):
        await session.send('略略略，我主人把你拉黑了。哈↑哈↑哈')
        return

    keyWord = session.get('keyWord', prompt='请输入您要解密的梦境')
    apii = Shadiao.ZhouInterprets(keyWord=keyWord)
    await session.send(apii.get_content())

@nonebot.on_command('反码', only_to_me=False)
async def reverseCode(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    key_word = ctx['raw_message']
    message_list = key_word.split()
    if len(message_list) == 1:
        await session.send('没有可反码内容！')
        return

    key_word = message_list[1]
    if_group = False
    if 'group_id' in ctx:
        if_group = True
        idNum = ctx['group_id']
    else:
        idNum = ctx['user_id']

    bot = nonebot.get_bot()

    if if_group:
        await bot.send_msg(message_type='group', group_id=idNum, message=key_word, auto_escape=True)
    else:
        await bot.send_msg(message_type='private', user_id=idNum, message=key_word, auto_escape=True)

@nonebot.on_command('好好说话', only_to_me=False)
async def can_you_be_fucking_normal(session : nonebot.CommandSession):
    start_time = time.time()
    ctx = session.ctx.copy()
    key_word = session.get('key_word', prompt='请输入一个关键词！')
    key_word = str(key_word)
    try:
        await session.send(await hhsh(key_word) + '\n本次查询耗时： %.2fs' % (time.time() - start_time))
        if 'group_id' in ctx:
            sanity_meter.set_user_data(ctx['user_id'], 'hhsh')

    except Exception as e:
        nonebot.logger.debug('Something went wrong %s' % e)

@can_you_be_fucking_normal.args_parser
@getYouDaoService.args_parser
@jpToJpDict.args_parser
@nico_send.args_parser
@zhou_interprets.args_parser
async def _youDaoServiceArgs(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('词呢！词呢！！KORA！！！')

async def hhsh(entry : str) -> str:
    if cache.check_exist(entry, HHSHMEANING):
        return cache.get_result(entry, HHSHMEANING)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
        'Origin': 'https://lab.magiconch.com',
        'referer': 'https://lab.magiconch.com/nbnhhsh/'
    }

    guess_url = 'https://lab.magiconch.com/api/nbnhhsh/guess'

    try:
        page = requests.post(guess_url, data={"text": entry}, headers=headers, timeout=5)
    except Exception as e:
        print(e)
        return '出问题了，请重试！'

    json_data = page.json()
    result = '这个缩写可能的意味有：\n'
    try:
        for idx, element in enumerate(json_data[0]['trans']):
            result += element + ', ' if idx + 1 != len(json_data[0]['trans']) else element
    except KeyError:
        try:
            return result + json_data[0]['inputting'][0]
        except KeyError:
            return '这……我也不懂啊草，能不能好好说话（'

    cache.store_result(entry, result, HHSHMEANING)
    return result
