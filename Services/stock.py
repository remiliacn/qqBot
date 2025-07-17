from datetime import datetime
from os import getcwd
from time import time_ns

from PIL import Image, ImageDraw, ImageFont

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


async def text_to_image(string: str):
    line_char_count = 50 * 2  # 每行字符数：30个中文字符(=60英文字符)
    char_size = 36
    table_width = 4
    padding = 50  # Padding in pixels

    def line_break(line):
        ret = ''
        width = 0
        for char in line:
            if len(char.encode('utf8')) == 3:  # 中文
                if line_char_count == width + 1:  # 剩余位置不够一个汉字
                    width = 2
                    ret += '\n' + char
                else:  # 中文宽度加2
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
    text_height = char_size * lines

    # Create image with padding
    image_width = text_width + padding * 2
    image_height = text_height + padding * 2

    image = Image.new("L", (image_width, image_height), "white")
    draw_table = ImageDraw.Draw(im=image)

    # Draw text with offset for padding
    draw_table.text(xy=(padding, padding), text=output_str, fill='#000000', font=d_font, spacing=4)

    file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
    image.save(file_name)
    image.close()

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
