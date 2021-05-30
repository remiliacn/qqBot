from datetime import datetime, timedelta
from os import getcwd
from time import time_ns

import pandas
import plotly.graph_objects as plotter
import requests
from plotly.subplots import make_subplots


class Stock:
    def __init__(self, code):
        self.code = code
        self.stock_name = '未知股票'
        self.kline_api_1 = f'http://push2his.eastmoney.com/api/qt/stock/kline/' \
                           f'get?fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6' \
                           f'&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56' \
                           f'%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61' \
                           f'&klt=101&fqt=1&secid=0.{code}' \
                           f'&beg={(datetime.now() - timedelta(days=120)).strftime("%Y%m%d")[0:8]}' \
                           f'&end={((datetime.now()).strftime("%Y%m%d"))[0:8]}'
        self.kline_api_2 = f'http://push2his.eastmoney.com/api/qt/stock/kline/' \
                           f'get?fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6' \
                           f'&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56' \
                           f'%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61' \
                           f'&klt=101&fqt=1&secid=1.{code}' \
                           f'&beg={(datetime.now() - timedelta(days=120)).strftime("%Y%m%d")[0:8]}' \
                           f'&end={((datetime.now()).strftime("%Y%m%d"))[0:8]}'

    def get_kline_map(self) -> str:
        kline_data_temp = self._request_for_kline_data()
        if not kline_data_temp:
            return ''

        kline_data = [x.split(',') for x in kline_data_temp]
        # [['2021-05-28', '89.81', '90.58', '95.00', '88.86', '527020', '4870749696.00', '6.95', '2.51', '2.22', '4.84']

        open_data = [x[1] for x in kline_data]
        close_data = [float(x[2]) for x in kline_data]

        change_rate = [float(x[-2]) for x in kline_data]
        volume_color = ['red' if x > 0 else 'green' for x in change_rate]

        close_data_frame = pandas.DataFrame([float(x[2]) for x in kline_data])
        high_data = [x[3] for x in kline_data]
        low_data = [x[4] for x in kline_data]

        # Moving average
        ma5_data = self._get_moving_average_data(close_data_frame, 5)
        ma10_data = self._get_moving_average_data(close_data_frame, 10)
        ma20_data = self._get_moving_average_data(close_data_frame, 20)

        # Volume
        volume_data = [int(x[5]) for x in kline_data]

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
                f'股票名称：{self.stock_name}',
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
        volume_trace = plotter.Bar(
            y=volume_data,
            marker_color=volume_color
        )

        # histogram
        histogram_graph = plotter.Bar(
            y=histogram,
            marker_color=histogram_color
        )

        # MACD line
        macd_graph = plotter.Scatter(
            y=self._convert_data_frame_to_list(macd_data),
            line=dict(color='red', width=1)
        )

        # MACD signal
        signal_line = plotter.Scatter(
            y=self._convert_data_frame_to_list(signal),
            line=dict(color='blue', width=1)
        )

        # Candlestick graph
        plot.add_trace(candle_trace, row=1, col=1)
        plot.add_trace(ma5_trace, row=1, col=1)
        plot.add_trace(ma10_trace, row=1, col=1)
        plot.add_trace(ma20_trace, row=1, col=1)

        # Volume graph
        plot.add_trace(volume_trace, row=2, col=1)

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
        file_name = f'{getcwd()}/data/bot/stock/{int(time_ns())}.png'
        plot.write_image(file_name)
        return file_name


    def _get_moving_average_data(self, df, time: int):
        temp = df.rolling(time).mean()
        return self._convert_data_frame_to_list(temp)

    @staticmethod
    def _convert_data_frame_to_list(df):
        temp = df.values.tolist()
        return [x for element in temp for x in element]

    def _request_for_kline_data(self, api=1) -> list:
        if api == 1:
            page = requests.get(self.kline_api_1)
        else:
            page = requests.get(self.kline_api_2)

        json_data = page.json()
        if json_data is None:
            return []

        if 'data' not in json_data:
            return []

        json_data = json_data['data']
        if json_data is None and api == 1:
            klines_data = self._request_for_kline_data(api=2)
            return klines_data

        elif api == 2 and json_data is None:
            return []

        if 'name' in json_data:
            self.stock_name = json_data['name']

        if 'klines' in json_data:
            return json_data['klines']

        return []


if __name__ == '__main__':
    s = Stock('603881')
    print(s.get_kline_map())
