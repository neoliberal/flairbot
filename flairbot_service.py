"""daemon runner"""
import os

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
    )

    while True:
        bot.fetch_pms()

if __name__ == "__main__":
    main()
