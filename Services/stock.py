import re
from datetime import datetime, timedelta
from os import getcwd
from time import time_ns

import aiohttp
import pandas
import plotly.graph_objects as plotter
import requests
from PIL import Image, ImageDraw, ImageFont
from plotly.subplots import make_subplots

import Services.okex.spot_api as spot
from config import OKEX_API_KEY, OKEX_PASSPHRASE, OKEX_SECRET_KEY


async def text_to_image(string: str):
    line_char_count = 50 * 2  # 每行字符数：30个中文字符(=60英文字符)
    char_size = 30
    table_width = 4

    def line_break(line):
        ret = ''
        width = 0
        for char in line:
            if len(char.encode('utf8')) == 3:  # 中文
                if line_char_count == width + 1:  # 剩余位置不够一个汉字
                    width = 2
                    ret += '\n' + char
                else:  # 中文宽度加2，注意换行边界
                    width += 2
                    ret += char
            else:
                if char == '\t':
                    space_c = table_width - width % table_width  # 已有长度对TABLE_WIDTH取余
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

    output_str = string
    output_str = line_break(output_str)
    d_font = ImageFont.truetype('C:/Windows/Fonts/Deng.ttf', char_size)
    lines = output_str.count('\n')

    image = Image.new("L", (line_char_count * char_size // 2, char_size * lines), "white")
    draw_table = ImageDraw.Draw(im=image)
    draw_table.text(xy=(0, 0), text=output_str, fill='#000000', font=d_font, spacing=4)

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


def do_plot(
        open_data,
        close_data,
        volume_data,
        high_data,
        low_data,
        stock_name,
        volume_color,
        analyze_type='MACD'
):
    plot = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            f'股票名称：{stock_name}',
            "成交量",
            analyze_type
        ),
        row_heights=[0.5, 0.2, 0.3]
    )

    close_data_frame = pandas.DataFrame(close_data)
    # Moving average
    ma5_data = _get_moving_average_data(close_data_frame, 5)
    ma10_data = _get_moving_average_data(close_data_frame, 10)
    ma20_data = _get_moving_average_data(close_data_frame, 20)

    market_will = '无法判断'

    if analyze_type == 'MACD':
        # MACD
        ema_12_data = close_data_frame.ewm(span=12, adjust=False).mean()
        ema_26_data = close_data_frame.ewm(span=26, adjust=False).mean()

        macd_data = ema_12_data - ema_26_data
        signal = macd_data.ewm(span=9, adjust=False).mean()

        histogram = macd_data - signal
        histogram = histogram.values.tolist()
        histogram = [x for element in histogram for x in element]
        histogram_color = ['green' if x < 0 else 'red' for x in histogram]

        macd_data = _convert_data_frame_to_list(macd_data)
        signal_data = _convert_data_frame_to_list(signal)

        for i in range(1, len(macd_data) - 1):
            prev_macd = round(macd_data[i - 1], 3)
            next_macd = round(macd_data[i + 1], 3)

            prev_signal = round(signal_data[i - 1], 3)
            next_signal = round(signal_data[i + 1], 3)

            if prev_macd <= prev_signal \
                    and next_macd >= next_signal:
                market_will = '检测到MACD金叉，买入信号'

            elif prev_macd >= prev_signal \
                    and next_macd <= next_signal:
                market_will = '检测到MACD死叉，卖出信号'

        # histogram
        histogram_graph = plotter.Bar(
            y=histogram,
            marker_color=histogram_color
        )

        # MACD line
        macd_graph = plotter.Scatter(
            y=macd_data,
            line=dict(color='red', width=1)
        )

        # MACD signal
        signal_line = plotter.Scatter(
            y=signal_data,
            line=dict(color='blue', width=1)
        )

        # MACD graph
        plot.add_trace(histogram_graph, row=3, col=1)
        plot.add_trace(macd_graph, row=3, col=1)
        plot.add_trace(signal_line, row=3, col=1)

    elif analyze_type == '买卖意愿':
        high_open = [float(x) - float(y) for x, y in zip(high_data, open_data)]
        open_low = [float(x) - float(y) for x, y in zip(open_data, low_data)]

        ar_data = []
        for idx, _ in enumerate(high_open):
            high_open_sum = sum(high_open[0: idx + 1])
            open_low_sum = sum(open_low[0: idx + 1])
            ar_data.append(high_open_sum / open_low_sum * 100)

        mean_data = round(
            sum(ar_data[len(ar_data) // 2:]) / len(ar_data[len(ar_data) // 2:])
        )
        if ar_data[-1] < mean_data:
            market_will = '市场意愿偏空'
        elif ar_data[-1] == mean_data:
            market_will = '市场意愿震荡'
        else:
            market_will = '市场意愿偏多'

        ar_trace = plotter.Scatter(
            y=ar_data,
            line=dict(color='red', width=1)
        )

        plot.add_trace(ar_trace, row=3, col=1)

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
    volume_trace = plotter.Bar(
        y=volume_data,
        marker_color=volume_color
    )

    # Candlestick graph
    plot.add_trace(candle_trace, row=1, col=1)
    plot.add_trace(ma5_trace, row=1, col=1)
    plot.add_trace(ma10_trace, row=1, col=1)
    plot.add_trace(ma20_trace, row=1, col=1)

    # Volume graph
    plot.add_trace(volume_trace, row=2, col=1)

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
    return plot, market_will


class Crypto:
    def __init__(self, crypto: str):
        self.crypto = f'{crypto.upper()}-USDT'
        self.granularity = 60 * 60

    def get_kline(self, analyze_type='MACD'):
        spot_api = spot.SpotAPI(
            OKEX_API_KEY,
            OKEX_SECRET_KEY,
            OKEX_PASSPHRASE,
            False
        )

        # get 1h k-line
        json_data = spot_api.get_kline(
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
        plot, market_will = do_plot(
            open_data,
            close_data,
            volume_data,
            high_data,
            low_data,
            self.crypto,
            volume_color,
            analyze_type
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name, market_will


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

    async def get_kline_map(self, analyze_type='MACD') -> (str, str):
        kline_data = await self._request_for_kline_data()
        if not kline_data:
            return '', ''

        open_data = [x[1] for x in kline_data]
        close_data = [float(x[2]) for x in kline_data]

        change_rate = [float(x[-2]) for x in kline_data]
        volume_color = ['red' if x > 0 else 'green' for x in change_rate]

        high_data = [x[3] for x in kline_data]
        low_data = [x[4] for x in kline_data]

        # Volume
        volume_data = [int(x[5]) for x in kline_data]

        plot, market_will = do_plot(
            open_data,
            close_data,
            volume_data,
            high_data,
            low_data,
            self.stock_name,
            volume_color,
            analyze_type
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name, market_will

    async def _request_for_kline_data(self, iteration=False) -> list:
        async with aiohttp.ClientSession() as client:
            async with client.get(self.kline_api) as page:
                json_data = await page.json()

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

        return []
