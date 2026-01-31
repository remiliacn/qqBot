import asyncio
from datetime import datetime
from os import getcwd
from time import time_ns

from PIL import Image, ImageDraw, ImageFont

from Services.util.file_utils import delete_file_after

MA_EFFECTIVE_POINT = -5


def _is_cross_relation(list1, list2, i):
    return is_cross_relation(list1[i - 1], list2[i - 1], list1[i], list2[i], list1[i + 1], list2[i + 1])


def is_dtpl(list1, list2, i):
    return list1[i - 1] >= list2[i - 1] and list1[i] >= list2[i] and list1[i + 1] >= list2[i + 1]


def is_ktpl(list1, list2, i):
    return list1[i - 1] <= list2[i - 1] and list1[i] <= list2[i] and list1[i + 1] <= list2[i + 1]


def is_cross_relation(*args) -> bool:
    values = [round(x, 3) for x in args]
    try:
        return values[0] < values[1] and values[2] <= values[3] and values[4] > values[5]
    except IndexError:
        return False


def is_trading_hour(is_crypto: bool) -> bool:
    if is_crypto:
        return True

    time_now = datetime.now()
    if time_now.weekday() >= 5:
        return False

    if time_now.hour < 9:
        return False

    if time_now.hour == 9 and time_now.minute < 20:
        return False

    if time_now.hour >= 15:
        return False

    return True


async def text_to_image(string: str) -> str:
    line_char_count = 50 * 2
    char_size = 36
    table_width = 4
    padding = 75
    line_spacing = 12
    corner_radius = 25
    shadow_width = 12
    accent_height = 6

    def line_break(line: str) -> str:
        ret = ''
        width = 0
        for char in line:
            if len(char.encode('utf8')) == 3:
                if line_char_count == width + 1:
                    width = 2
                    ret += '\n' + char
                else:
                    width += 2
                    ret += char
            else:
                if char == '\t':
                    space_c = table_width - width % table_width
                    ret += ' ' * space_c
                    width += space_c
                elif char == '\n':
                    width = 0
                    ret += char
                else:
                    width += 1
                    ret += char
            if width >= line_char_count:
                ret += '\n'
                width = 0
        if ret.endswith('\n'):
            return ret
        return ret + '\n'

    output_str = line_break(string)
    d_font = ImageFont.truetype('data/util/Deng.ttf', char_size)
    lines = output_str.count('\n')

    text_width = line_char_count * char_size // 2
    text_height = (char_size + line_spacing) * lines

    content_width = text_width + padding * 2
    content_height = text_height + padding * 2 + accent_height

    image_width = content_width + shadow_width * 2
    image_height = content_height + shadow_width * 2

    gradient_start = (20, 25, 40)
    gradient_end = (30, 35, 55)

    image = Image.new("RGB", (image_width, image_height), gradient_start)

    for y in range(image_height):
        ratio = y / image_height
        r = int(gradient_start[0] * (1 - ratio) + gradient_end[0] * ratio)
        g = int(gradient_start[1] * (1 - ratio) + gradient_end[1] * ratio)
        b = int(gradient_start[2] * (1 - ratio) + gradient_end[2] * ratio)
        for x in range(image_width):
            image.putpixel((x, y), (r, g, b))

    draw_table = ImageDraw.Draw(im=image, mode="RGBA")

    shadow_color = (10, 15, 30, 80)
    for offset in range(shadow_width, 0, -1):
        alpha = int(80 * (1 - offset / shadow_width))
        draw_table.rounded_rectangle(
            [
                (shadow_width - offset, shadow_width - offset),
                (image_width - shadow_width + offset, image_height - shadow_width + offset)
            ],
            radius=corner_radius,
            fill=(*shadow_color[:3], alpha)
        )

    main_box = [
        (shadow_width, shadow_width),
        (image_width - shadow_width, image_height - shadow_width)
    ]
    draw_table.rounded_rectangle(main_box, radius=corner_radius, fill=(35, 45, 70, 250), outline=(70, 130, 220),
                                 width=3)

    accent_color = (100, 180, 255)
    accent_box = [
        (shadow_width + corner_radius, shadow_width),
        (image_width - shadow_width - corner_radius, shadow_width + accent_height)
    ]
    draw_table.rounded_rectangle(accent_box, radius=3, fill=accent_color)

    draw_table.text(
        xy=(shadow_width + padding, shadow_width + padding + accent_height),
        text=output_str,
        fill=(220, 230, 250),
        font=d_font,
        spacing=line_spacing
    )

    file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
    image.save(file_name)
    image.close()

    asyncio.create_task(delete_file_after(file_name, 5 * 60))

    return file_name


def _convert_nest_loop_to_single(lis):
    return [x for element in lis for x in element]


def _convert_data_frame_to_list(df):
    temp = df.values.tolist()
    return _convert_nest_loop_to_single(temp)


def _get_moving_average_data(df, time: int):
    temp = df.rolling(time).mean()
    return _convert_data_frame_to_list(temp)


def _ma_comparison(ma_5, ma_10, ma_20):
    ma_5 = round(ma_5, 5)
    ma_10 = round(ma_10, 5)
    ma_20 = round(ma_20, 5)

    return ma_5 == ma_10 or ma_10 == ma_20
