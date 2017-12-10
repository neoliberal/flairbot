"""flairbot"""
import logging

from slack_python_logging import slack_logger

from changer.changer import FlairChanger
from page.updater import WikiUpdater
from stats.updater import StatisticsUpdater

class Flairbot(object):
    def __init__() -> None:
        logger: logging.Logger = slack_logger.initialize("flairbot")
        return

    def run() -> None: