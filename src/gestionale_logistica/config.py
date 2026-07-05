import configparser
from pathlib import Path

CONFIG_PATH = Path("config.ini")


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config
