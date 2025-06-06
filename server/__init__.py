import os
import sys
try:
    import usocket as socket
except ModuleNotFoundError:
    import socket
from .utils import *


class Headers(object):
    _content_type = None

    def __init__(self, data: str | dict | None = None):
        if isinstance(data, str):
            for i in data.split('\n'):
                key = i.split(': ')[0].strip('\r')
                value = i.split(': ')[-1].strip('\r')
                if key:
                    setattr(self, self._parsing_keys(key), value if not key == value else '')
        elif isinstance(data, dict):
            for key, value in data.items():
                if not isinstance(value, str):
                    raise ValueError(f'value in header most be str not {value.__class__.__name__}')
                setattr(self, self._parsing_keys(key), value)

    def __getattr__(self, item):
        if item in self.__dict__.keys():
            return self.__dict__[item]

    def __setattr__(self, key, value):
        self.__dict__[str(key)] = str(value)

    def _parsing_keys(self, ky: str):
        return ky.replace('-', '_')

    def to_dict(self):
        aas = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                aas[key.replace('_', '-')] = value
        return aas

    def sendheders(self, soc: socket.Socket, status: int = 200, status_str: str = 'ok'):
        soc.send(f'HTTP/1.1 {status} {status_str.upper()}\n'.encode())
        for k, v in self.to_dict().items():
            soc.send(f'{k}: {v}\n'.encode())
        soc.send('\n')

    def __str__(self):
        return f'{self.__class__.__name__}(\n' + '\n    '.join(
            [f'{key}={repr(value)}' for key, value in self.__dict__.items()]) + '\n)'


class RenderTemplate:
    _html = ''
    _statusCode = None
    _file_type = None

    def __init__(self, html: str, statusCode: int = 200, **kwargs):
        if self.check_if_is_file(html):
            os.chdir(configs.get('root', '/'))
            with open(html) as file:
                self._html = file.read()
                if html.split('.')[-1] in ['avif', 'webp', 'png']:
                    self._file_type = 'image/' + html.split('.')[-1]
        else:
            self._html = html
        self._statusCode = statusCode
        self.replace_text_ifany(**kwargs)

    def __call__(self, soc: socket.Socket, header: Headers):
        if not hasattr(header, 'Content_Type'):
            header.Content_Type = 'text/html'
        elif self._file_type:
            header.Content_Type = self._file_type
        header.Content_Length = str(len(self._html))
        header.sendheders(soc, status=self._statusCode, status_str=status_code.get(self._statusCode) or 'NOT FOUND')
        soc.sendall(self._html.encode())

    def check_if_is_file(self, fl: str, cwd=None):
        if not cwd:
            if configs.get('root', '/') not in os.getcwd():
                try:
                    os.chdir(configs.get('root', '/'))
                except:
                    pass
            cwd = os.getcwd()
        try:
            for i in os.listdir():
                if os.getcwd().replace(configs.get('root', '/'), '') == fl:
                    return True
                try:
                    os.chdir(i)
                    return self.check_if_is_file(fl, os.getcwd())
                except:
                    continue
            else:
                return False
        finally:
            os.chdir(cwd)

    def find_curawal(self, num=2):
        start = '{'
        end = '}'
        html = self._html
        is_none = False
        rss = []
        while not is_none:
            anu = None
            stt = html.find(start*num)
            ent = html.find(end*num)
            if stt != -1 and ent != -1 and (ent-stt) <= 30:
                anu = html[stt:ent+num]
            if anu is None:
                is_none = True
            else:
                rss.append(anu)
                html = html.replace(anu, '')
        return rss

    def replace_text_ifany(self, **kwargs):
        params = self.find_curawal()
        for param in params:
            par = param.strip('{').strip('}').strip()
            if par in kwargs.keys():
                self._html = self._html.replace(param, kwargs.get(par))


class Server:
    _headers = None
    _handler = []
    request = None

    def __init__(self, debug=False):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.bind(('', 80))
        self.soc.listen(5)
        self.debug = debug
        self._headers = Headers({'Connection': 'close'})

    def _addHandler(self, path, method, param, cb):
        self._handler.append((path, method, param, cb))

    def route(self, path: str, method: str, param: dict | None = None):
        return lambda cb: self._addHandler(path, method, param, cb)

    def execute(self):
        conn, method, path, headers, data = self.read()
        for pt, mt, param, cb in self._handler:
            if method in mt:
                if pt == path:
                    self.request = Request(method, path, data, headers)
                    pt = ParsingPath(pt)
                    prm = pt.getparam(path)
                    if prm:
                        res = cb(**prm)
                    else:
                        res = cb()
                    self._headers.Content_Type = headers.Content_Type
                    if isinstance(res, RenderTemplate):
                        res(conn, self._headers)
                    else:
                        self._headers.Content_Length = str(len(json.dumps(res))) if isinstance(res, dict) else str(len(str(res)))
                        self._headers.sendheders(conn)
                        conn.sendall(json.dumps(res) if isinstance(res, dict) else str(res))
                else:
                    RenderTemplate('<!DOCTYPE html>\n<html lang="en"><head><title>404 NOT FOUND</title><body><h1>404 NOT FOUND</h1></body></head></html>',
                                   statusCode=404)(conn, self._headers)
        else:
            RenderTemplate('<!DOCTYPE html>\n<html lang="en"><head><title>404 NOT FOUND</title><body><h1>404 NOT FOUND</h1></body></head></html>',
                           statusCode=404)(conn, self._headers)

    def run(self):
        while True:
            try:
                self.execute()
            except Exception as e:
                sys.print_exception(e)
                continue

    def close(self):
        self.soc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.soc.close()

    def read(self, length=1024):
        adr = self.soc.accept()
        data = None
        if adr:
            conn, addr = adr
            if self.debug:
                print('Got a connection from %s' % str(addr))
            conn.settimeout(10)
            request = conn.recv(length).decode()
            if self.debug:
                print('Content = %s' % request)
            mod, head = request.split('\n')[0], request.split('\n')[1:]
            method, path, scm = mod.split(' ')
            path = ParsingPath(path)
            headers = Headers('\n'.join(head))
            if method == 'POST':
                if headers.Content_Type == 'application/x-www-form-urlencoded':
                    data = urldecode(conn.recv(int(headers.Content_Length)).decode())
                elif headers.Content_Type == 'application/json':
                    data = json.loads(conn.recv(int(headers.Content_Length)).decode())
                elif hasattr(headers, 'Content_Length'):
                    data = conn.recv(int(headers.Content_Length)).decode()
                if self.debug:
                    print('data:', data)
            return conn, method, path, headers, data


def render_template(html, status: int = 200, **kwargs):
    return RenderTemplate(html, status, **kwargs)
