import configparser
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.main_window import MainWindow

CONFIG_PATH = Path("config.ini")


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config


def setup_logging(config: configparser.ConfigParser) -> None:
    logging.basicConfig(
        level=config.get("logging", "level", fallback="INFO"),
        filename=config.get("logging", "file", fallback="app.log"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    config = load_config()
    setup_logging(config)
    logging.getLogger(__name__).info("Avvio Gestionale Logistica")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
