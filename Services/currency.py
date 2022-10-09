from re import findall

from Services.util.common_util import HttpxHelperClient


class Currency:
    def __init__(self, amount: float, source_currency: str, target_currency=None):
        self.target_currency = source_currency if target_currency is None else target_currency

        self.currency_url = f'https://currency-converter-calculator.com/convert/' \
                            f'{source_currency}/' \
                            f'{self.target_currency}/{amount}'

        self.amount = amount
        self.client = HttpxHelperClient()
        self.source_currency = source_currency

    async def get_currency_result(self) -> str:
        page = await self.client.get(self.currency_url)
        texts = page.text
        result = list(set(findall(r'%s %s = \d+\.?\d* [A-Z]+' % (self.amount, self.source_currency), texts)))

        return '\n'.join(result)
