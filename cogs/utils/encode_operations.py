import base64
import urllib

from cogs.utils.brainduck import Translator


class EncodeOperations:
    @staticmethod
    def url_encode(message):
        # v lel pycharm
        # noinspection PyUnresolvedReferences
        return urllib.parse.quote_plus(message)

    @staticmethod
    def base64_encode(message):
        return base64.encodebytes(
            str.encode(message)
        ).decode(encoding='utf-8').strip()

    @staticmethod
    def encode_brainduck(message):
        translator = Translator(buf=message)
        return translator.get_init_code() + translator.read_all()

    @staticmethod
    def encode_binary(message):
        return ''.join(format(ord(x), 'b') for x in message)
