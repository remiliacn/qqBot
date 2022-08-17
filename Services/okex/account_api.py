from .client import Client
from .consts import *


class AccountAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False, first=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test, first)

    # get all currencies list
    async def get_currencies(self):
        return await self._request_without_params(GET, CURRENCIES_INFO)

    # get wallet info
    async def get_wallet(self):
        return await self._request_without_params(GET, WALLET_INFO)

    # get specific currency info
    async def get_currency(self, currency):
        return await self._request_without_params(GET, CURRENCY_INFO + str(currency))

    # coin withdraw
    async def coin_withdraw(self, currency, amount, destination, to_address, trade_pwd, fee):
        params = {'currency': currency, 'amount': amount, 'destination': destination, 'to_address': to_address,
                  'trade_pwd': trade_pwd, 'fee': fee}
        return await self._request_with_params(POST, COIN_WITHDRAW, params)

    # query the fee of coin withdraw
    async def get_coin_fee(self, currency=''):
        params = {}
        if currency:
            params['currency'] = currency
        return await self._request_with_params(GET, COIN_FEE, params)

    # query all recently coin withdraw record
    async def get_coins_withdraw_record(self):
        return await self._request_without_params(GET, COINS_WITHDRAW_RECORD)

    # query specific coin withdraw record
    async def get_coin_withdraw_record(self, currency):
        return await self._request_without_params(GET, COIN_WITHDRAW_RECORD + str(currency))

    # query ledger record
    async def get_ledger_record(self, currency='', after='', before='', limit='', type=''):
        params = {}
        if currency:
            params['currency'] = currency
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        if type:
            params['type'] = type
        return await self._request_with_params(GET, LEDGER_RECORD, params, cursor=True)

    # query top up address
    async def get_top_up_address(self, currency):
        params = {'currency': currency}
        return await self._request_with_params(GET, TOP_UP_ADDRESS, params)

    async def get_asset_valuation(self, account_type='', valuation_currency=''):
        params = {}
        if account_type:
            params['account_type'] = account_type
        if valuation_currency:
            params['valuation_currency'] = valuation_currency
        return await self._request_with_params(GET, ASSET_VALUATION, params)

    async def get_sub_account(self, sub_account):
        params = {'sub-account': sub_account}
        return await self._request_with_params(GET, SUB_ACCOUNT, params)

    # query top up records
    async def get_top_up_records(self):
        return await self._request_without_params(GET, COIN_TOP_UP_RECORDS)

    # query top up record
    async def get_top_up_record(self, currency, after='', before='', limit=''):
        params = {}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return await self._request_without_params(GET, COIN_TOP_UP_RECORD + str(currency))

    # coin transfer
    async def coin_transfer(self, currency, amount, account_from, account_to, type='', sub_account='', instrument_id='',
                            to_instrument_id=''):
        params = {'currency': currency, 'amount': amount, 'from': account_from, 'to': account_to}
        if type:
            params['type'] = type
        if sub_account:
            params['sub_account'] = sub_account
        if instrument_id:
            params['instrument_id'] = instrument_id
        if to_instrument_id:
            params['to_instrument_id'] = to_instrument_id
        return await self._request_with_params('POST', COIN_TRANSFER, params)
