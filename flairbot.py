"""Set user flairs."""
from configparser import ConfigParser
import logging
from typing import Optional, Tuple, FrozenSet, List

import praw

from slackbot.python_logging.slack_logger import make_slack_logger

class Flairbot(object):
    """Main class"""

    def __init__(self, reddit: praw.Reddit, subreddit: str) -> None:
        """Initial setup"""
        def get_config() -> ConfigParser:
            """returns config"""
            self.logger.debug("Creating config")
            parser: ConfigParser = ConfigParser(allow_no_value=True)

            self.logger.debug("Getting config")
            config_str: str = self.subreddit.wiki["flairbot/config"].content_md
            if config_str:
                self.logger.debug("Got config")
                parser.read_string(config_str)
            else:
                self.logger.error("No config found")

            self.logger.debug("config created")
            return parser

        self.logger: logging.Logger = make_slack_logger("flairbot")
        self.reddit: praw.Reddit = reddit
        self.subreddit: praw.models.Subreddit = self.reddit.subreddit(subreddit)
        self.config = get_config()
        self.text_flairs: FrozenSet[str] = frozenset(
            self.config["types"]
        )
        self.flairs = self.get_flairs()
        self.logger.info("Flairbot initalized successfully")

    def get_flairs(self) -> ConfigParser:
        """fetches flairs"""
        self.logger.debug("Fetching flairs")
        flairs: ConfigParser = ConfigParser()
        flairs_str: str = self.subreddit.wiki["flairbot/config/flairs"].content_md
        if flairs_str:
            self.logger.debug("Fetched flairs")
            flairs.read_string(flairs_str)
        else:
            self.logger.critical("No flairs found. Aborting.")
            import sys
            sys.exit(0)
        return flairs

    def fetch_pms(self) -> None:
        """Get PMs for account"""
        import prawcore

        try:
            for message in self.reddit.inbox.unread():
                author: str = str(message.author)
                if message.subject == self.config["messages"]["subject"]:
                    self.logger.debug("Processing request \"%s\" for /u/%s", message, author)
                    self.process_pm(message)
        except prawcore.exceptions.RequestException:
            self.logger.exception("Request error: Sleeping for 60 seconds.")
            import time
            time.sleep(60)

    def process_pm(self, message: praw.models.Message) -> None:
        """Process the PMs"""
        self.logger.debug("Updating flairs")
        self.flairs = self.get_flairs()
        self.logger.debug("Updated flairs")

        flair: str = message.body
        result: Optional[Tuple[str, str, str]] = self.get_flair_properties(flair)
        message.mark_read()
        if result is None:
            self.send_pm_failure(message)
            return

        self.set_flair(message.author, result[0], result[1], result[2])

    def get_flair_properties(self, flair: str) -> Optional[Tuple[str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """
        self.logger.debug("Getting flair properties")
        try:
            section: str = next(
                (section for section in self.flairs.sections()
                 if flair in self.flairs.options(section))
            )
        except StopIteration:
            self.logger.warning("Flair \"%s\" does not exist", flair)
            return None

        text: str = self.flairs[section][flair]
        self.logger.debug("Got flair properties")
        return (section, flair, text)

    # pylint: disable=R0201
    def send_pm_failure(self, message: praw.models.Message):
        """pms user informing flair selection is invalid"""
        user: praw.models.Redditor = message.author

        self.logger.debug("Sending PM to /u/%s", user)
        message_str: str = (
            f"Your flair selection \"{message.body}\" was invalid."
            "Flairs can be found on the sidebar."
        )

        user.message(
            subject="Flair update failed",
            message=message_str
        )

        self.logger.debug("PM sent to /u/%s", user)
        return

    def set_flair(self, user: praw.models.Redditor, section: str, flair: str, text: str):
        """Set the flairs"""

        for current_user_flair in self.subreddit.flair(redditor=user):
            self.logger.debug("Setting flair for /u/%s", user)
            current_class: Optional[str] = current_user_flair["flair_css_class"]
            decomposed_class: List[str] = [] if current_class is None else current_class.split(' ')
            current_text: str = current_user_flair["flair_text"]

            new_class: List[str] = []

            special: bool = False
            for text_flair in self.text_flairs:
                if text_flair in decomposed_class:
                    self.logger.debug("/u/%s is special", user)
                    special = True
                    new_class.append(text_flair)
                    break

            new_class.extend([section, flair, "image"])
            new_text: str = current_text if special else text
            combined_class: str = " ".join(new_class)
            self.subreddit.flair.set(
                redditor=user,
                text=new_text,
                css_class=combined_class
            )
            self.logger.debug("Flair for /u/%s changed to \"%s\" (%s)",
                              user, new_text, combined_class
                             )
