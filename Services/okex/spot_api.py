from .client import Client
from .consts import *


class SpotAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False, first=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test, first)

    # query spot account info
    def get_account_info(self):
        return self._request_without_params(GET, SPOT_ACCOUNT_INFO)

    # query specific coin account info
    def get_coin_account_info(self, currency):
        return self._request_without_params(GET, SPOT_COIN_ACCOUNT_INFO + str(currency))

    # query ledger record not paging
    def get_ledger_record(self, currency, after='', before='', limit='', type=''):
        params = {}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        if type:
            params['type'] = type
        return self._request_with_params(GET, SPOT_LEDGER_RECORD + str(currency) + '/ledger', params, cursor=True)

    # take order
    def take_order(self, instrument_id, side, client_oid='', type='', size='', price='', order_type='0', notional=''):
        params = {'instrument_id': instrument_id, 'side': side, 'client_oid': client_oid, 'type': type, 'size': size, 'price': price, 'order_type': order_type, 'notional': notional}
        return self._request_with_params(POST, SPOT_ORDER, params)

    def take_orders(self, params):
        return self._request_with_params(POST, SPOT_ORDERS, params)

    # revoke order
    def revoke_order(self, instrument_id, order_id='', client_oid=''):
        params = {'instrument_id': instrument_id}
        if order_id:
            return self._request_with_params(POST, SPOT_REVOKE_ORDER + str(order_id), params)
        elif client_oid:
            return self._request_with_params(POST, SPOT_REVOKE_ORDER + str(client_oid), params)

    def revoke_orders(self, params):
        return self._request_with_params(POST, SPOT_REVOKE_ORDERS, params)

    # query orders list v3
    def get_orders_list(self, instrument_id, state, after='', before='', limit=''):
        params = {'instrument_id': instrument_id, 'state': state}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, SPOT_ORDERS_LIST, params, cursor=True)

    # query order info
    def get_order_info(self, instrument_id, order_id='', client_oid=''):
        params = {'instrument_id': instrument_id}
        if order_id:
            return self._request_with_params(GET, SPOT_ORDER_INFO + str(order_id), params)
        elif client_oid:
            return self._request_with_params(GET, SPOT_ORDER_INFO + str(client_oid), params)

    def get_orders_pending(self, instrument_id, after='', before='', limit=''):
        params = {'instrument_id': instrument_id}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, SPOT_ORDERS_PENDING, params, cursor=True)

    def get_fills(self, instrument_id, order_id='', after='', before='', limit=''):
        params = {'instrument_id': instrument_id}
        if order_id:
            params['order_id'] = order_id
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, SPOT_FILLS, params, cursor=True)

    # take order_algo
    def take_order_algo(self, instrument_id, mode, order_type, size, side, trigger_price='', algo_price='', algo_type='',
                        callback_rate='', algo_variance='', avg_amount='', limit_price='', sweep_range='',
                        sweep_ratio='', single_limit='', time_interval=''):
        params = {'instrument_id': instrument_id, 'mode': mode, 'order_type': order_type, 'size': size, 'side': side}
        if order_type == '1':  # 止盈止损参数
            params['trigger_price'] = trigger_price
            params['algo_price'] = algo_price
            if algo_type:
                params['algo_type'] = algo_type
        elif order_type == '2':  # 跟踪委托参数
            params['callback_rate'] = callback_rate
            params['trigger_price'] = trigger_price
        elif order_type == '3':  # 冰山委托参数（最多同时存在6单）
            params['algo_variance'] = algo_variance
            params['avg_amount'] = avg_amount
            params['limit_price'] = limit_price
        elif order_type == '4':  # 时间加权参数（最多同时存在6单）
            params['sweep_range'] = sweep_range
            params['sweep_ratio'] = sweep_ratio
            params['single_limit'] = single_limit
            params['limit_price'] = limit_price
            params['time_interval'] = time_interval
        return self._request_with_params(POST, SPOT_ORDER_ALGO, params)

    # cancel_algos
    def cancel_algos(self, instrument_id, algo_ids, order_type):
        params = {'instrument_id': instrument_id, 'algo_ids': algo_ids, 'order_type': order_type}
        return self._request_with_params(POST, SPOT_CANCEL_ALGOS, params)

    def get_trade_fee(self):
        return self._request_without_params(GET, SPOT_TRADE_FEE)

    # get order_algos
    def get_order_algos(self, instrument_id, order_type, status='', algo_id='', before='', after='', limit=''):
        params = {'instrument_id': instrument_id, 'order_type': order_type}
        if status:
            params['status'] = status
        elif algo_id:
            params['algo_id'] = algo_id
        if before:
            params['before'] = before
        if after:
            params['after'] = after
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, SPOT_GET_ORDER_ALGOS, params)

    # query spot coin info
    def get_coin_info(self):
        return self._request_without_params(GET, SPOT_COIN_INFO)

    # query depth
    def get_depth(self, instrument_id, size='', depth=''):
        params = {}
        if size:
            params['size'] = size
        if depth:
            params['depth'] = depth
        return self._request_with_params(GET, SPOT_DEPTH + str(instrument_id) + '/book', params)

    # query ticker info
    def get_ticker(self):
        return self._request_without_params(GET, SPOT_TICKER)

    # query specific ticker
    def get_specific_ticker(self, instrument_id):
        return self._request_without_params(GET, SPOT_SPECIFIC_TICKER + str(instrument_id) + '/ticker')

    def get_deal(self, instrument_id, limit=''):
        params = {}
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, SPOT_DEAL + str(instrument_id) + '/trades', params)

    # query k-line info
    def get_kline(self, instrument_id, start='', end='', granularity=''):
        params = {}
        if start:
            params['start'] = start
        if end:
            params['end'] = end
        if granularity:
            params['granularity'] = granularity
        # 按时间倒叙 即由结束时间到开始时间
        return self._request_with_params(GET, SPOT_KLINE + str(instrument_id) + '/candles', params)

        # 按时间正序 即由开始时间到结束时间
        # data = self._request_with_params(GET, SPOT_KLINE + str(instrument_id) + '/candles', params)
        # return list(reversed(data))

    def get_history_kline(self, instrument_id, start='', end='', granularity=''):
        params = {}
        if start:
            params['start'] = start
        if end:
            params['end'] = end
        if granularity:
            params['granularity'] = granularity
        return self._request_with_params(GET, SPOT_KLINE + str(instrument_id) + '/history' + '/candles', params)
