from asyncio import sleep, get_running_loop
from base64 import b64encode
from collections.abc import Mapping
from functools import lru_cache
from hashlib import sha1
from math import ceil
from mimetypes import guess_extension
from os import remove, getcwd, path
from os.path import exists
from random import randint
from ssl import SSLContext
from time import time
from typing import List, Literal, Dict, Any, Union, TypeVar
from uuid import uuid4

import markdown2
import numpy as np
from PIL import Image, ImageDraw
from httpx import AsyncClient, Response
from lxml import html
from lxml.html.clean import Cleaner
from matplotlib import pyplot as plt, patches
from matplotlib.colors import colorConverter
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Message
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from playwright.async_api import async_playwright
from tqdm import tqdm

from Services.util.ctx_utility import get_user_id, get_group_id
from Services.util.file_utils import delete_file_after
from awesome.Constants.path_constants import BOT_RESPONSE_PATH
from model.common_model import Status

TEMP_FILE_DIRECTORY = path.join(getcwd(), 'data', 'temp')
T = TypeVar("T")


def chunk_string(string: str, length: int):
    return (string[0 + i:length + i] for i in range(0, len(string), length))


def _compile_forward_node(self_id: int, data: Message) -> MessageSegment:
    return MessageSegment.node_custom(user_id=self_id, nickname='月朗风清', content=data)


def calculate_sha1_string(input_str: str) -> str:
    sha1_hash = sha1()

    sha1_hash.update(input_str.encode('utf-8-sig'))
    return sha1_hash.hexdigest()


def calculate_sha1(file_path: str) -> str:
    sha1_hash = sha1()

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha1_hash.update(byte_block)

    return sha1_hash.hexdigest()


def base64_encode_image(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        return b64encode(f.read()).decode('utf-8')


async def slight_adjust_pic_and_get_path(input_path: str) -> str:
    logger.info(f'Starting to sightly adjust the image: {input_path}')
    edited_path = path.join(TEMP_FILE_DIRECTORY, f'{uuid4().hex}.{input_path.split(".")[-1]}')
    try:
        with Image.open(input_path) as image:
            draw = ImageDraw.Draw(image)
            x = randint(0, max(image.width - 3, 0))
            y = randint(0, max(image.height - 3, 0))
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill='white', outline='black')
            image.save(edited_path)

        loop = get_running_loop()
        loop.create_task(delete_file_after(edited_path, 120))
    except Exception as err:
        logger.error(f'Failed to micro modify a pixiv pic. {err.__class__}')
        return input_path

    logger.success(f'Adjusting image successfully completed for: {input_path}')
    return edited_path


async def autorevoke_message(
        bot: Bot, group_id: int,
        message_type_to_send: Literal['forward', 'normal'], message: Message, revoke_interval: int = 50) -> None:
    if message_type_to_send == 'forward':
        message_data: Dict[str, Any] = await bot.send_group_forward_msg(
            group_id=group_id,
            messages=message
        )
    else:
        message_data: Dict[str, Any] = await bot.send_group_msg(group_id=group_id, message=message)

    logger.info(f'Message data before revoking: {message_data}')
    message_id: int = message_data['message_id']
    loop = get_running_loop()
    loop.call_later(revoke_interval, loop.create_task, bot.delete_msg(message_id=message_id))


async def get_general_ctx_info(ctx: GroupMessageEvent | Mapping[str, Any]) -> tuple[int, int, int]:
    message_id = int(getattr(ctx, 'message_id', ctx.get('message_id')))
    return message_id, int(get_user_id(ctx)), int(get_group_id(ctx))


async def time_to_literal(time_string: int) -> str:
    if time_string < 0:
        suffix = '前'
    else:
        suffix = '后'

    time_string = abs(time_string)
    hour = time_string // 3600
    time_string %= 3600

    minute = time_string // 60
    second = time_string % 60

    result = ''
    day = 0
    if hour >= 24:
        day = hour // 24
        hour -= day * 24

    result += f'{day}日' if day > 0 else ''
    result += f'{hour}时' if hour > 0 else ''
    result += f'{minute}分' if minute > 0 else ''
    result += f'{second}秒'

    return result + suffix


def construct_timestamp_string(seconds: float, _pos=None) -> str:
    seconds = ceil(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return f'{hours:02}:{minutes:02}:{seconds:02}'


@lru_cache(maxsize=None)
def find_repeated_substring(input_str: str) -> str:
    if not input_str:
        return ''

    num_of_chars = len(input_str)
    prefix = [0] * num_of_chars
    j = 0
    for i in range(1, num_of_chars):
        while j > 0 and input_str[i] != input_str[j]:
            j = prefix[j - 1]
        if input_str[i] == input_str[j]:
            j += 1
        prefix[i] = j

    repeated_length = num_of_chars - prefix[-1]
    if repeated_length < num_of_chars and num_of_chars % repeated_length == 0:
        return input_str[:repeated_length]

    return input_str


def get_if_has_at_and_qq(event: GroupMessageEvent | PrivateMessageEvent) -> tuple[bool, str]:
    if isinstance(event, PrivateMessageEvent):
        return False, '0'

    at_qq_list = event.original_message.get('at')
    return len(at_qq_list) > 0, at_qq_list[0].data.get('qq', '0') if at_qq_list else '0'


def compile_forward_message(self_id: int, *args: List[MessageSegment]) -> Message:
    data_list: List[MessageSegment] = []
    for arg in args:
        data_list.append(_compile_forward_node(self_id, Message(arg)))

    return Message(data_list)


def is_float(content: str) -> bool:
    try:
        float(content)
        return True

    except ValueError:
        return False


async def check_if_number_user_id(session: Matcher, arg: str) -> str:
    if not arg.isdigit():
        await session.finish('输入非法')

    return arg


def markdown_to_html(string: str):
    string = string.replace('```c#', '```').replace('&#91;', '[').replace('&#93;', ']')
    is_html = html.fromstring(string).find('.//*') is not None
    if is_html:
        cleaner = Cleaner(safe_attrs=html.defs.safe_attrs | {'style'})
        cleaner.javascript = True
        cleaner.style = False

        string = cleaner.clean_html(string)

        logger.info(f'Cleaned string: {string}')

    html_string = markdown2.markdown(
        string, extras=['fenced-code-blocks', 'strike', 'tables', 'task_list', 'code-friendly'])

    file_name = f'{getcwd()}/data/bot/response/{int(time())}.html'
    with open(file_name, 'w+', encoding='utf-8') as file:
        file.write(r"""
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        extensions: ["tex2jax.js", "AMSmath.js"],
        jax: ["input/TeX", "output/HTML-CSS"],
        tex2jax: {
            inlineMath: [ ['$','$'] ],
            displayMath: [ ['$$','$$'] ],
            processEscapes: true
        },
    });
</script>
<style>
p { font-size: 25px }
ul { font-size: 25px }
ol { font-size: 25px }
pre { font-size: 20px !important }
</style>
<script type="text/javascript" src="https://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
</script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/default.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap.min.css"
 integrity="sha384-HSMxcRTRxnN+Bdg0JdbxYKrThecOKuH5zCYotlSAcp1+c8xmyTe9GYg1l9a69psu" crossorigin="anonymous">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>

""" + f'<body><div class="container">{html_string}</div></body>')

    return file_name


async def html_to_image_async(file_name: str, run_hljs: bool = False, render_spotify_iframe: str = '') -> str:
    file_name_png = path.join(BOT_RESPONSE_PATH, f'{file_name.split("/")[-1]}.png')
    if exists(file_name_png):
        return file_name_png

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(device_scale_factor=3.0)

            await page.goto(f'file:///{file_name}', wait_until='networkidle', timeout=10000)

            if run_hljs:
                await page.evaluate("hljs.highlightAll();")
                try:
                    await page.wait_for_selector(
                        "#MathJax_Message[style*='display: none']",
                        timeout=5000
                    )
                except Exception:
                    logger.warning('Render markdown exceeded time limit.')

            if render_spotify_iframe:
                try:
                    logger.info('Trying to switch to iframe')
                    frame = page.frame_locator(f"#{render_spotify_iframe}")
                    await frame.locator("button").wait_for(timeout=8000)
                except Exception:
                    logger.warning('Render iframe exceeded time limit.')

            await page.wait_for_function(
                """
                () => {
                    const images = document.getElementsByTagName('img');
                    if (images.length === 0) return true;
                    for (let img of images) {
                        if (!img.complete || img.naturalHeight === 0) {
                            return false;
                        }
                    }
                    return true;
                }
                """, timeout=30000)
            logger.info('All images loaded successfully.')

            element = await page.query_selector('.container')
            if element:
                await element.screenshot(path=file_name_png, type='png')
            else:
                await page.screenshot(path=file_name_png, type='png', full_page=True)

            await browser.close()

        if exists(file_name):
            remove(file_name)

        return file_name_png
    except Exception as err:
        logger.error(f"Playwright rendering failed ({err.__class__.__name__}): {err}")
        raise


async def markdown_to_image(text: str) -> Status:
    try:
        html_file = markdown_to_html(text)
        image_path = await html_to_image_async(html_file)
        return Status(is_success=True, message=image_path)
    except Exception as err:
        logger.error(f'Markdown render failed {err.__class__}')
        return Status(is_success=False, message='渲染出错力')


def gradient_fill(x: List[float], y: List[float] | np.ndarray, fill_color=None, ax=None, zfunc=None, **kwargs):
    if ax is None:
        ax = plt.gca()

    line, = ax.plot(x, y, **kwargs)
    if fill_color is None:
        fill_color = line.get_color()

    zorder = line.get_zorder()
    alpha = line.get_alpha()
    alpha = 1.0 if alpha is None else alpha

    if zfunc is None:
        h, w = 100, 1
        z = np.empty((h, w, 4), dtype=float)
        rgb = colorConverter.to_rgb(fill_color)
        z[:, :, :3] = rgb
        z[:, :, -1] = np.linspace(0, alpha, h)[:, None]
    else:
        z = zfunc(x, y, fill_color=fill_color, alpha=alpha)
    xmin, xmax, ymin, ymax = min(x), max(x), min(y), max(y)
    # noinspection PyTypeChecker
    im = ax.imshow(z, aspect='auto', extent=[xmin, xmax, ymin, ymax],
                   origin='lower', zorder=zorder)

    xy = np.column_stack([x, y])
    xy = np.vstack([[xmin, ymin], xy, [xmax, ymin], [xmin, ymin]])
    clip_path = patches.Polygon(xy, facecolor='none', edgecolor='none', closed=True)
    ax.add_patch(clip_path)
    im.set_clip_path(clip_path)
    ax.autoscale(True)
    return line, im


class OptionalDict:
    def __init__(self, anything=None):
        self.anything = anything

    def map(self, key) -> 'OptionalDict':
        if self.anything is not None and key in self.anything:
            return OptionalDict(self.anything[key])

        return OptionalDict()

    def or_else(self, data: T) -> T:
        if self.anything is None:
            return data

        return self.anything


class HttpxHelperClient:
    def __init__(self, headers=None):
        if headers is None:
            self.headers = {
                'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/84.0.4147.125 Safari/537.36'
            }
        else:
            self.headers = headers

        self.context = SSLContext()
        ciphers = ":".join([
            "@SECLEVEL=1",  # python 3.10 default is SECLEVEL=2 which rejects less secure ciphers
            "ALL",
        ])
        self.context.set_ciphers(ciphers)

    async def get(self, url: str, timeout=5.0, headers=None, cookies=None, redirect=False) -> Response:
        headers = headers if headers is not None else self.headers

        async with AsyncClient(timeout=timeout, headers=headers, cookies=cookies) as client:
            return await client.get(url, follow_redirects=redirect)

    async def post(self, url: str, json: dict, headers=None, timeout=10.0) -> Response:
        headers = headers if headers is not None else self.headers
        async with AsyncClient(headers=headers, timeout=timeout, default_encoding='utf-8') as client:
            return await client.post(url, json=json)

    async def download(self, url: str, file_name: Union[str, bytes],
                       timeout=20.0, headers=None, retry=0) -> str:
        file_name = file_name.replace('\\', '/')
        headers = headers if headers is not None else self.headers
        if retry > 5:
            logger.error('Retry exceeds the limit')
            return ''

        try:
            async with AsyncClient(timeout=timeout, headers=headers, verify=self.context) as client:
                async with client.stream('GET', url=url, follow_redirects=True) as response:
                    ext = guess_extension(response.headers['Content-Type'].strip())
                    if ext:
                        file_name = f'{file_name}{ext}'

                    if not exists(file_name):
                        logger.info(f'Downloading file name: {file_name.split("/")[-1]}')
                        if response.status_code == 403:
                            logger.warning(f'Download retry: {retry + 1}, url: {url}')
                            await sleep(15 * (retry + 1))
                            return await self.download(url, file_name, timeout, headers, retry + 1)
                        file_size = int(
                            response.headers['Content-Length']) if 'Content-Length' in response.headers else 0
                        with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as progress:
                            with open(file_name, 'wb') as file:
                                async for chunk in response.aiter_bytes():
                                    file.write(chunk)
                                    progress.update(len(chunk))

            return file_name.__str__()
        except Exception as err:
            logger.warning(f'Download failed in common util download: {err.__class__}')
            if exists(file_name):
                logger.warning("Retrying...")
                remove(file_name)

            await self.download(url, file_name, timeout, headers, retry + 1)

        return ''
