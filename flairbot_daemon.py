"""daemon runner"""
import daemon

from flairbot import Flairbot

def main() -> None:
    """main function"""
    import os
    import praw

    reddit: praw.Reddit = praw.Reddit(
        client_id=os.environ["client_id"],
        client_secret=os.environ["client_secret"],
        refresh_token=os.environ["request_token"]
    )
    bot: Flairbot = Flairbot(
        reddit,
        "neoliberal",
        os.environ["url"]
    )
    with daemon.DaemonContext():
        bot.fetch_pms()
    return

if __name__ == "__main__":
    main()
