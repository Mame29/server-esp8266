configs = {
    'root': 'templates',
    'static': 'static'
}

status_code = {
    200: 'OK',
    404: 'NOT FOUND',
    405: 'FORBIDEN'
}


def unquote(string):
    if not string:
        return b''

    if isinstance(string, str):
        string = string.encode('utf-8')

    bits = string.split(b'%')
    if len(bits) == 1:
        return string

    res = bytearray(bits[0])
    append = res.append
    extend = res.extend

    for item in bits[1:]:
        try:
            append(int(item[:2], 16))
            extend(item[2:])
        except KeyError:
            append(b'%')
            extend(item)

    return bytes(res)


def urldecode(quote: bytes | str) -> dict:
    if not quote:
        return {}
    if isinstance(quote, bytes):
        quote = quote.decode()
    als = {}
    for i in quote.split('&'):
        if len(i.split('=')) == 2:
            key, value = i.split('=')
            key = unquote(key.strip(' ').replace('+', ' ')).decode()
            value = unquote(value.strip(' ').replace('+', ' ')).decode()
            if value.startswith('{') and value.endswith('}'):
                try:
                    value = json.loads(unquote(value))
                except ValueError:
                    pass
            als[key] = value
    return als


def quotes(string: str):
    if not isinstance(string, str):
        if string is not None:
            string = str(string)
        else:
            raise TypeError()
    dic = {"%21": "!", "%22": '"', "%23": "#", "%24": "$", "%26": "&", "%27": "'", "%28": "(", "%29": ")", "%2A": "*",
           "%2B": "+", "%2C": ",", "%2F": "/", "%3A": ":", "%3B": ";", "%3D": "=", "%3F": "?", "%40": "@", "%5B": "[",
           "%5D": "]", "%7B": "{", "%7D": "}"}
    for key, value in dic.items():
        string = string.replace(value, key)
    return string


def urlencode(quote: dict):
    if not isinstance(quote, dict):
        raise ValueError(f'parameter quote most be dict not {quote.__name__}')

    alp = []
    for key, value in quote.items():
        alp.append(f'{quotes(key).replace(" ", "+")}={quotes(value).replace(" ", "+")}')
    return '&'.join(alp)