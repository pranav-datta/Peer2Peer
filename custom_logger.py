import logging


class CustomLogger(object):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CustomLogger, cls).__new__(cls)
            logging.basicConfig(filename='logs.log', format="%(message)s", level=logging.DEBUG)
            cls.logger = logging.getLogger()
        return cls._instance