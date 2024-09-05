from typing import Any, Union


def fetch_one_or_default(fetch_one_result: Union[list, tuple], default_value: Any) -> Any:
    return fetch_one_result[0] if fetch_one_result and fetch_one_result[0] else default_value
