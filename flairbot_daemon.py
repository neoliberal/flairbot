"""daemon runner"""
import logging
import os

import daemon
from daemon import pidfile
import praw

from flairbot import Flairbot

def main() -> None:
    """main function"""

    reddit: praw.Reddit = praw.Reddit(
        client_id=os.environ["client_id"],
        client_secret=os.environ["client_secret"],
        refresh_token=os.environ["refresh_token"],
        user_agent="linux:flairbot:v3.0 (by /u/CactusChocolate)"
    )

    bot: Flairbot = Flairbot(
        reddit,
        "neoliberal",
        os.environ["slack_webhook_url"]
    )

    file_handler: logging.Handler = logging.FileHandler("/var/log/flairbot.log")
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_handler.setFormatter(logging.Formatter(format_string))
    file_handler.setLevel(logging.DEBUG)
    bot.logger.addHandler(file_handler)

    with daemon.DaemonContext(
        working_directory="/var/lib/flairbot",
        umask=0o002,
        pidfile=pidfile.TimeoutPIDLockFile(
            "/var/run/flairbot.pid")
        ) as context:
        while context.is_open:
            bot.fetch_pms()

if __name__ == "__main__":
    main()
