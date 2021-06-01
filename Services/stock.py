import re
from datetime import datetime, timedelta
from os import getcwd
from time import time_ns
from PIL import Image, ImageDraw, ImageFont

import Services.okex.spot_api as spot

import pandas
import plotly.graph_objects as plotter
import requests
from plotly.subplots import make_subplots

from config import OKEX_API_KEY, OKEX_PASSPHRASE, OKEX_SECRET_KEY


async def text_to_image(string: str):
    LINE_CHAR_COUNT = 50 * 2  # 每行字符数：30个中文字符(=60英文字符)
    CHAR_SIZE = 30
    TABLE_WIDTH = 4

    def line_break(line):
        ret = ''
        width = 0
        for char in line:
            if len(char.encode('utf8')) == 3:  # 中文
                if LINE_CHAR_COUNT == width + 1:  # 剩余位置不够一个汉字
                    width = 2
                    ret += '\n' + char
                else:  # 中文宽度加2，注意换行边界
                    width += 2
                    ret += char
            else:
                if char == '\t':
                    space_c = TABLE_WIDTH - width % TABLE_WIDTH  # 已有长度对TABLE_WIDTH取余
                    ret += ' ' * space_c
                    width += space_c
                elif char == '\n':
                    width = 0
                    ret += char
                else:
                    width += 1
                    ret += char
            if width >= LINE_CHAR_COUNT:
                ret += '\n'
                width = 0
        if ret.endswith('\n'):
            return ret
        return ret + '\n'

    output_str = string
    output_str = line_break(output_str)
    d_font = ImageFont.truetype('C:/Windows/Fonts/Deng.ttf', CHAR_SIZE)
    lines = output_str.count('\n')

    image = Image.new("L", (LINE_CHAR_COUNT * CHAR_SIZE // 2, CHAR_SIZE * lines), "white")
    draw_table = ImageDraw.Draw(im=image)
    draw_table.text(xy=(0, 0), text=output_str, fill='#000000', font=d_font, spacing=4)

    file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
    image.save(file_name)
    image.close()

    return file_name


def _convert_nest_loop_to_single(l):
    return [x for element in l for x in element]


def _convert_data_frame_to_list(df):
    temp = df.values.tolist()
    return _convert_nest_loop_to_single(temp)


def _get_moving_average_data(df, time: int):
    temp = df.rolling(time).mean()
    return _convert_data_frame_to_list(temp)


def do_plot(
        open_data,
        close_data,
        volume_data,
        high_data,
        low_data,
        stock_name,
        volume_color
):
    close_data_frame = pandas.DataFrame(close_data)
    # Moving average
    ma5_data = _get_moving_average_data(close_data_frame, 5)
    ma10_data = _get_moving_average_data(close_data_frame, 10)
    ma20_data = _get_moving_average_data(close_data_frame, 20)

    # MACD
    ema_12_data = close_data_frame.ewm(span=12, adjust=False).mean()
    ema_26_data = close_data_frame.ewm(span=26, adjust=False).mean()

    macd_data = ema_12_data - ema_26_data
    signal = macd_data.ewm(span=9, adjust=False).mean()

    histogram = macd_data - signal
    histogram = histogram.values.tolist()
    histogram = [x for element in histogram for x in element]
    histogram_color = ['green' if x < 0 else 'red' for x in histogram]

    plot = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            f'股票名称：{stock_name}',
            "成交量",
            "MACD"
        )
    )

    # K-line
    candle_trace = plotter.Candlestick(
        open=open_data,
        high=high_data,
        low=low_data,
        close=close_data,
        increasing={
            'line': {
                'color': 'red'
            }
        },
        decreasing={
            'line': {
                'color': 'green'
            }
        }
    )

    # Moving average lines.
    ma5_trace = plotter.Scatter(
        y=ma5_data,
        line=dict(color='orange', width=1)
    )
    ma10_trace = plotter.Scatter(
        y=ma10_data,
        line=dict(color='blue', width=1)
    )
    ma20_trace = plotter.Scatter(
        y=ma20_data,
        line=dict(color='red', width=1)
    )

    # Volume graph.
    volume_data_frame = pandas.DataFrame(volume_data)
    ma5_volume_data = _get_moving_average_data(volume_data_frame, 5)
    ma10_volume_data = _get_moving_average_data(volume_data_frame, 10)

    volume_trace = plotter.Bar(
        y=volume_data,
        marker_color=volume_color
    )

    volume_ma5_trace = plotter.Scatter(
        y=ma5_volume_data,
        line=dict(color='red', width=1)
    )

    volume_ma10_trace = plotter.Scatter(
        y=ma10_volume_data,
        line=dict(color='blue', width=1)
    )

    # histogram
    histogram_graph = plotter.Bar(
        y=histogram,
        marker_color=histogram_color
    )

    # MACD line
    macd_graph = plotter.Scatter(
        y=_convert_data_frame_to_list(macd_data),
        line=dict(color='red', width=1)
    )

    # MACD signal
    signal_line = plotter.Scatter(
        y=_convert_data_frame_to_list(signal),
        line=dict(color='blue', width=1)
    )

    # Candlestick graph
    plot.add_trace(candle_trace, row=1, col=1)
    plot.add_trace(ma5_trace, row=1, col=1)
    plot.add_trace(ma10_trace, row=1, col=1)
    plot.add_trace(ma20_trace, row=1, col=1)

    # Volume graph
    plot.add_trace(volume_trace, row=2, col=1)
    plot.add_trace(volume_ma5_trace, row=2, col=1)
    plot.add_trace(volume_ma10_trace, row=2, col=1)

    # MACD graph
    plot.add_trace(histogram_graph, row=3, col=1)
    plot.add_trace(macd_graph, row=3, col=1)
    plot.add_trace(signal_line, row=3, col=1)

    plot.update_layout(
        {
            'xaxis': {
                'rangeslider': {
                    'visible': False
                }
            }
        }
    )

    plot.update_layout(showlegend=False)
    return plot


class Crypto:
    def __init__(self, crypto: str):
        self.crypto = f'{crypto.upper()}-USDT'
        self.granularity = 60 * 60

    def get_kline(self):
        spotAPI = spot.SpotAPI(
            OKEX_API_KEY,
            OKEX_SECRET_KEY,
            OKEX_PASSPHRASE,
            False
        )

        # get 1h k-line
        json_data = spotAPI.get_kline(
            instrument_id=self.crypto,
            start='',
            end='',
            granularity=self.granularity
        )[:90]

        self.crypto += ' （1h）'
        json_data = list(json_data)
        json_data.reverse()

        open_data = [float(x[1]) for x in json_data]
        high_data = [x[2] for x in json_data]
        low_data = [x[3] for x in json_data]
        close_data = [float(x[4]) for x in json_data]
        volume_data = [float(x[5]) for x in json_data]

        volume_color = [
            'red' if (c - o) > 0 else 'green' for c, o in zip(close_data, open_data)
        ]
        plot = do_plot(
            open_data,
            close_data,
            volume_data,
            high_data,
            low_data,
            self.crypto,
            volume_color
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name


class Stock:
    def __init__(self, code, keyword=''):
        self.code = code
        self.stock_name = '未知股票'
        self.type = -1

        if str(self.code).isdigit() and re.match(r'\d{6}', self.code):
            self.type = 1

        elif re.match(r'BK\d{4}', self.code):
            self.type = 90

        elif re.match(r'[A-Z]+', self.code):
            self.type = 106

        elif re.match(r'\d{5}', self.code):
            self.type = 116

        else:
            self.type = 0

        self.kline_api = self.get_api_link(self.type)

        self.guba_api = None
        if keyword:
            self.guba_api = f'http://searchapi.eastmoney.com/bussiness/web/' \
                            f'QuotationLabelSearch?' \
                            f'token=REMILIACN&keyword={keyword}&type=0&pi=1&ps=30'

    def get_api_link(self, type_code) -> str:
        return f'http://15.push2his.eastmoney.com/api/qt/stock/kline/get?' \
               f'secid={type_code}.{self.code}&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6' \
               f'&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2' \
               f'Cf59%2Cf60%2Cf61&klt=101&fqt=1' \
               f'&beg={(datetime.now() - timedelta(days=120)).strftime("%Y%m%d")[0:8]}' \
               f'&end={((datetime.now()).strftime("%Y%m%d"))[0:8]}'

    async def get_stock_codes(self) -> str:
        if self.guba_api is None:
            return ''

        page = requests.get(self.guba_api)
        json_data = page.json()
        if not json_data['IsSuccess']:
            return '请求API失败'

        if 'Data' not in json_data:
            return 'Data键值丢失'

        json_data = json_data['Data']
        if not json_data:
            return '搜索无有效数据'

        stock = {}

        # Type: 1 -> AB股， 2 -> 指数， 3 -> 板块，
        # 4 -> 港股， 5 -> 美股， 6 -> 英股， 7 -> 三板，
        # 8 -> 基金， 9 -> 债券， 10 -> 期货期权， 11 -> 外汇
        for element in json_data:
            if 'Name' not in element or 'Type' not in element:
                continue

            stock_type = element['Name']
            type_id = element['Type']
            data = element['Datas']
            if not data or type_id == 6:
                continue

            stock[stock_type] = data

        response = ''
        for key, element in stock.items():
            response += f'{key}: \n'
            for e in element:
                response += f'{e["Name"]}： {e["Code"]}\n'

            response += '\n'

        response = await text_to_image(response)
        return response

    async def get_kline_map(self) -> str:
        kline_data = await self._request_for_kline_data()
        if not kline_data:
            return ''

        open_data = [x[1] for x in kline_data]
        close_data = [float(x[2]) for x in kline_data]

        change_rate = [float(x[-2]) for x in kline_data]
        volume_color = ['red' if x > 0 else 'green' for x in change_rate]

        high_data = [x[3] for x in kline_data]
        low_data = [x[4] for x in kline_data]

        # Volume
        volume_data = [int(x[5]) for x in kline_data]

        plot = do_plot(
            open_data,
            close_data,
            volume_data,
            high_data,
            low_data,
            self.stock_name,
            volume_color
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name

    async def _request_for_kline_data(self, iteration=False) -> list:
        page = requests.get(self.kline_api)

        json_data = page.json()
        if json_data is None:
            return []

        if 'data' not in json_data:
            return []

        json_data = json_data['data']
        if json_data is None:
            # Iter once to use the other API to try to fetch the kline data.
            if not iteration:
                if self.type == 106:
                    self.kline_api = self.get_api_link(107)
                else:
                    self.kline_api = self.get_api_link(0)

                return await self._request_for_kline_data(iteration=True)

            return []

        if 'name' in json_data:
            self.stock_name = json_data['name']

        if 'klines' in json_data:
            json_data = json_data['klines']
            return [x.split(',') for x in json_data]
            # [['2021-05-28', '89.81', '90.58', '95.00', '88.86', '527020', '4870749696.00', '6.95', '2.51', '2.22', '4.84']

        return []


if __name__ == '__main__':
    c = Stock('234567', keyword='d')
    print(c.get_stock_codes())
