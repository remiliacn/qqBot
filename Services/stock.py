import json
from datetime import datetime, timedelta
from os import getcwd
from time import time_ns
from typing import Union

import pandas
import plotly.graph_objects as plotter
from PIL import Image, ImageDraw, ImageFont
from loguru import logger
from plotly.subplots import make_subplots

import Services.okex.spot_api as spot
from Services.util.common_util import HttpxHelperClient
from config import OKEX_API_KEY, OKEX_PASSPHRASE, OKEX_SECRET_KEY

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
    d_font = ImageFont.truetype(f'data/util/Deng.ttf', char_size)
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


def _ma_comparison(ma_5, ma_10, ma_20):
    ma_5 = round(ma_5, 5)
    ma_10 = round(ma_10, 5)
    ma_20 = round(ma_20, 5)

    return ma_5 == ma_10 or ma_10 == ma_20


def do_plot(
        open_data,
        close_data,
        close_data_for_ma,
        high_data,
        low_data,
        stock_name,
        analyze_type='MACD'
):
    plot = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f'股票名称：{stock_name}',
            analyze_type
        ),
        row_heights=[0.75, 0.25]
    )

    close_data_frame = pandas.DataFrame(close_data_for_ma)
    # Moving average
    if close_data_frame.size > 20:
        ma5_data = _get_moving_average_data(close_data_frame, 5)[20:]
        ma10_data = _get_moving_average_data(close_data_frame, 10)[20:]
        ma20_data = _get_moving_average_data(close_data_frame, 20)[20:]
    else:
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

        point_of_no_return = len(macd_data) * .8

        for i in range(1, len(macd_data) - 1):
            prev_macd = round(macd_data[i - 1], 3)
            next_macd = round(macd_data[i + 1], 3)

            prev_signal = round(signal_data[i - 1], 3)
            next_signal = round(signal_data[i + 1], 3)

            if prev_macd <= prev_signal \
                    and next_macd >= next_signal:
                market_will = f'检测到MACD金叉，买入信号{"（信号发出时间较早，可能已失效）" if i < point_of_no_return else ""}'

            elif prev_macd >= prev_signal \
                    and next_macd <= next_signal:
                market_will = f'检测到MACD死叉，卖出信号{"（信号发出时间较早，可能已失效）" if i < point_of_no_return else ""}'

        last_10_ma_5 = ma5_data[MA_EFFECTIVE_POINT:]
        last_10_ma_10 = ma10_data[MA_EFFECTIVE_POINT:]
        last_10_ma_20 = ma20_data[MA_EFFECTIVE_POINT:]

        market_will_ma = ''

        for i in range(1, len(last_10_ma_5) - 1):
            if _is_cross_relation(last_10_ma_5, last_10_ma_10, i):
                market_will_ma = '5日10日线金叉，买入信号\n'

            if _is_cross_relation(last_10_ma_10, last_10_ma_5, i):
                market_will_ma = '5日10日线死叉，卖出信号\n'

        second_last_i = len(last_10_ma_5) - 2
        if is_dtpl(last_10_ma_5, last_10_ma_10, second_last_i) \
                and is_dtpl(last_10_ma_10, last_10_ma_20, second_last_i) \
                and is_dtpl(last_10_ma_5, last_10_ma_20, second_last_i):
            market_will_ma += '均线多头排列，买入信号'

        elif is_ktpl(last_10_ma_20, last_10_ma_10, second_last_i) \
                and is_ktpl(last_10_ma_10, last_10_ma_5, second_last_i) \
                and is_ktpl(last_10_ma_20, last_10_ma_5, second_last_i):
            market_will_ma += '均线空头排列，卖出信号'

        line_break = "\n" if market_will_ma else ""
        market_will += f'{line_break}{market_will_ma}'

        # histogram
        # noinspection PyTypeChecker
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
        plot.add_trace(histogram_graph, row=2, col=1)
        plot.add_trace(macd_graph, row=2, col=1)
        plot.add_trace(signal_line, row=2, col=1)

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

        plot.add_trace(ar_trace, row=2, col=1)

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

    # Candlestick graph
    plot.add_trace(candle_trace, row=1, col=1)
    plot.add_trace(ma5_trace, row=1, col=1)
    plot.add_trace(ma10_trace, row=1, col=1)
    plot.add_trace(ma20_trace, row=1, col=1)

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
        self.crypto_name = crypto
        self.crypto_usdt = f'{crypto.upper()}-USDT'
        self.granularity = '1H'

    async def get_current_value(self):
        try:
            spot_api = spot.SpotAPI(OKEX_API_KEY, OKEX_SECRET_KEY, OKEX_PASSPHRASE)
            # get 1h k-line
            json_data = await spot_api.get_kline(instrument_id=self.crypto_usdt, bar=self.granularity)
            json_data = json_data[:90]
            open_data = [float(x[1]) for x in json_data][-1]

            return open_data
        except Exception as err:
            logger.warning(f'Seemly no crypto like this: {err}')
            return -1

    async def get_kline(self, analyze_type='MACD'):
        spot_api = spot.SpotAPI(OKEX_API_KEY, OKEX_SECRET_KEY, OKEX_PASSPHRASE)

        # get 1h k-line
        json_data = await spot_api.get_kline(instrument_id=self.crypto_usdt, bar=self.granularity)
        json_data = json_data[:90]

        self.crypto_usdt += ' （1h）'
        json_data = list(json_data)
        json_data.reverse()

        open_data = [float(x[1]) for x in json_data]
        high_data = [x[2] for x in json_data]
        low_data = [x[3] for x in json_data]
        close_data = [float(x[4]) for x in json_data]

        plot, market_will = do_plot(
            open_data[20:] if len(close_data) > 20 else open_data,
            close_data[20:] if len(close_data) > 20 else close_data,
            close_data,
            high_data[20:] if len(close_data) > 20 else high_data,
            low_data[20:] if len(close_data) > 20 else low_data,
            self.crypto_usdt,
            analyze_type
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name, market_will


class Stock:
    def __init__(self, code: str, keyword=''):
        self.code = code
        self.stock_name = '未知股票'

        self.kline_api = None
        self.type = None
        self.guba_api = None

        self.keyword = keyword

        if keyword:
            self.guba_api = f'http://searchapi.eastmoney.com/bussiness/web/' \
                            f'QuotationLabelSearch?' \
                            f'token=REMILIACN&keyword={keyword}&type=0&pi=1&ps=30'
            self.search_api = f'https://searchapi.eastmoney.com/api/suggest/get?input={self.keyword}' \
                              f'&type=14&token=D43BF722C8E33BDC906FB84D85E326E8'

        self.client = HttpxHelperClient()

    def get_api_link(self, type_code) -> str:
        return f'https://50.push2his.eastmoney.com/api/qt/stock/kline/get?' \
               f'secid={type_code}.{self.code}&ut=fa5fd1943c7b386f172d6893dbfba10b' \
               f'&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6' \
               f'&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2' \
               f'Cf59%2Cf60%2Cf61&klt=101&fqt=1&lmt=180' \
               f'&beg={(datetime.now() - timedelta(days=120)).strftime("%Y%m%d")[0:8]}' \
               f'&end={((datetime.now()).strftime("%Y%m%d"))[0:8]}'

    async def get_stock_codes(self, get_one=False) -> str:
        if self.guba_api is None:
            return ''

        response = await self.client.get(self.guba_api, timeout=None)
        json_data = response.json()
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

            if not get_one:
                if not data or type_id == 6:
                    continue

                stock[stock_type] = data
            else:
                if type_id < 6 and data:
                    self.type = int(data[0]['MktNum'])
                    return str(data[0]["Code"])

        response = ''
        for key, element in stock.items():
            response += f'{key}: \n'
            for e in element:
                response += f'{e["Name"]}： {e["Code"]}\n'

            response += '\n'

        response = await text_to_image(response)
        return response

    async def _host_detection(self) -> str:
        if not self.code.isdigit():
            return ''

        url = f'https://dcfm.eastmoney.com/em_mutisvcexpandinterface/api/js/get?type=' \
              f'QGQP_LSJGCYD&token=70f12f2f4f091e459a279469fe49eca5&ps=22&filter=(TRADECODE%3D%27{self.code}%27)'

        response = await self.client.get(url, timeout=None)
        try:
            json_data = response.text
            json_data = json.loads(json_data)
            json_data = json_data[0]
            host_strength = json_data['ZB']
            if host_strength > .4:
                host_s = '完全控盘'
            elif host_strength > 0.25:
                host_s = '中度控盘'
            elif host_strength > 0.1:
                host_s = '轻度控盘'
            else:
                host_s = '不控盘'
        except Exception as err:
            logger.warning(f'Maybe not stock code? {err}')
            return ''
        if not json_data:
            return ''

        return f'\n主力控盘迹象：{host_s}，资金流入：{json_data["ZLJLR"]:,.2f}（更新时间：{json_data["TRADEDATE"]}）'

    def set_type(self, any_type: Union[str, int]):
        self.type = any_type

    async def search_to_set_type_and_get_name(self) -> str:
        """
        Set stock type and return stock_name
        :return: stock_name: str
        """
        try_url = f'https://searchapi.eastmoney.com/api/suggest/get?input={self.code}' \
                  f'&type=14&token=D43BF722C8E33BDC906FB84D85E326E8'

        page = await self.client.get(try_url, timeout=None)
        try:
            data_response = page.json()
            self.set_type(int(data_response['QuotationCodeTable']['Data'][0]['MktNum']))
            self.code = data_response['QuotationCodeTable']['Data'][0]['Code']
            self.stock_name = data_response['QuotationCodeTable']['Data'][0]['Name']
            return data_response['QuotationCodeTable']['Data'][0]['Name']
        except (KeyError, IndexError, TypeError):
            return ''

    async def get_purchase_price(self, stock_type=None) -> (Union[int, float, None], str, float):
        """
        Return purchase_price, stock_name(zh), and price rate
        :param stock_type: stock_type, optional
        :return: purchase_price, stock_name, and a tuple where index=0 is high_rate, index=1 is low_rate
        """
        if stock_type is None:
            await self.search_to_set_type_and_get_name()
        else:
            self.type = stock_type

        if self.type is None or not str(self.type).isdigit():
            return -1, '', (10e6, -1000)

        data_url = f'https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=2&' \
                   f'fields=f43,f51,f52,f58,f60&secid={self.type}.{self.code}'

        response = await self.client.get(data_url, timeout=None)
        try:
            json_data = response.json()
            purchase_price = json_data['data']['f43']
            high_rate = json_data['data']['f51'] if 'f51' in json_data['data'] else 10e16
            low_rate = json_data['data']['f52'] if 'f52' in json_data['data'] else -1000
            if purchase_price == '-':
                purchase_price = json_data['data']['f60']
        except Exception as err:
            logger.warning(f'Error when getting first purchase price for stock: {self.code} -- {err}')
            return -1, '', (10e6, -1000)

        return purchase_price, self.stock_name, (high_rate, low_rate)

    async def get_kline_map(self, analyze_type='MACD') -> (str, str):
        self.kline_api = self.get_api_link(self.type)
        kline_data = await self._request_for_kline_data()
        if not kline_data:
            return '', ''

        open_data = [x[1] for x in kline_data]
        close_data = [float(x[2]) for x in kline_data]

        high_data = [x[3] for x in kline_data]
        low_data = [x[4] for x in kline_data]

        plot, market_will = do_plot(
            open_data[20:] if len(close_data) > 20 else open_data,
            close_data[20:] if len(close_data) > 20 else close_data,
            close_data,
            high_data[20:] if len(close_data) > 20 else high_data,
            low_data[20:] if len(close_data) > 20 else low_data,
            self.stock_name,
            analyze_type
        )
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)

        # host_detection = await self._host_detection()
        return file_name, market_will

    async def _request_for_kline_data(self) -> list:
        if self.code.isdigit():
            await self.search_to_set_type_and_get_name()

        self.kline_api = self.get_api_link(self.type)
        page = await self.client.get(self.kline_api, timeout=None)
        try:
            json_data = page.json()
        except Exception as err:
            logger.warning(f'Maybe not stock code? {err}')
            return []

        if json_data is None:
            return []

        if 'data' not in json_data:
            return []

        json_data = json_data['data']
        if json_data is None:
            return []

        if 'name' in json_data:
            self.stock_name = json_data['name']

        if 'klines' in json_data:
            json_data = json_data['klines']
            return [x.split(',') for x in json_data]

        return []
