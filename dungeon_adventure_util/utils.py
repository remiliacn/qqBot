from typing import Union


def get_data(x: dict, y: str) -> Union[any, None]:
    if x is None:
        return None

    return x[y] if y in x else None


def get_data_nested(x: dict, keys: list) -> Union[any, None]:
    for key in keys:
        if x is None:
            return None

        if key not in x:
            return None

        x = x[key]

    return x


def get_data_nested_int(x: dict, keys: list, is_return_none=False) -> Union[int, None]:
    data = get_data_nested(x, keys)
    if isinstance(data, int):
        return data

    return int(data) if data is not None and data.isdigit() else (None if is_return_none else 0)


def get_int_data(x: dict, y: str, default=0) -> int:
    data = get_data(x, y)
    return int(data) if data is not None and data.isdigit() else default
