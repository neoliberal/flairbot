"""daemon runner"""
import daemon
from daemon import pidfile

from flairbot import Flairbot

def main() -> None:
    """main function"""
    import os
    import praw

    reddit: praw.Reddit = praw.Reddit(
        client_id=os.environ["client_id"],
        client_secret=os.environ["client_secret"],
        refresh_token=os.environ["refresh_token"],
        user_agent="linux:flairbot:v3.0 (by /u/CactusChocolate)"
    )
    print("authenticated")
    bot: Flairbot = Flairbot(
        reddit,
        "neoliberal",
        os.environ["slack_webhook_url"]
    )
    print("created")
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
