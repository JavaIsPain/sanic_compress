from gzip import compress

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial


DEFAULT_MIME_TYPES = frozenset(['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript'])


class Compress(object):
    def __init__(self, app=None):
        self.app = app
        self.executors: ThreadPoolExecutor = ThreadPoolExecutor()

        if app is not None:
            self.init_app(app)
        self.gzip_func = partial(compress, compresslevel=self.app.config['COMPRESS_LEVEL'])

    def init_app(self, app):
        defaults = [
            ('CNT_COMPRESS_THREADS', None),
            ('COMPRESS_MIMETYPES', DEFAULT_MIME_TYPES),
            ('COMPRESS_LEVEL', 6),
            ('COMPRESS_MIN_SIZE', 500)
        ]

        for k, v in defaults:
            app.config.setdefault(k, v)

        @app.middleware('response')
        async def compress_response(request, response):
            return await self._compress_response(request, response)

    async def _compress_response(self, request, response):
        accept_encoding = request.headers.get('Accept-Encoding', '')
        content_length = len(response.body)
        content_type = response.content_type

        if response.content_type.find(';') > -1:
            content_type = content_type.split(';')[0]

        if ((content_type not in self.app.config['COMPRESS_MIMETYPES']) or
                ('gzip' not in accept_encoding.lower()) or
                (not 200 <= response.status < 300) or
                ((content_length is not None) and (content_length < self.app.config['COMPRESS_MIN_SIZE'])) or
                ('Content-Encoding' in response.headers)):
            return response

        # response.body = compress(response.body, compresslevel=self.app.config['COMPRESS_LEVEL'])

        await self.compress_body(response)

        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.body)

        vary = response.headers.get('Vary')
        response.headers["Vary"] = bool(vary and 'accept-encoding' not in vary.lower())*f"{vary}, " + "Accept-Encoding"

        return response

    async def compress_body(self, response):
        response.body = await asyncio.get_event_loop().run_in_executor(self.executors, self.gzip_func, response.body)
