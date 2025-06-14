import os
import datetime
import logging
import sys

# config values
# logging
__output_path_logs__ = "./logs/"


def init_logging(log_name: str = "temp", log_level: int = logging.DEBUG):
    os.makedirs(__output_path_logs__, exist_ok=True)
    currentDatetime = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    logging.basicConfig(filename=__output_path_logs__ + log_name + "-" + currentDatetime + '.log',
                        format='%(levelname)s : %(asctime)s - %(message)s\n', encoding='utf-8',
                        filemode='w', level=log_level)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
