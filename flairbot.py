"""Set user flairs."""
from configparser import ConfigParser
import logging
from typing import Match, Optional, Tuple, FrozenSet, List

import praw

from slackbot.python_logging.slack_logger import make_slack_logger

class Flairbot(object):
    """Main class"""

    def __init__(self, reddit: praw.Reddit, subreddit: str) -> None:
        """Initial setup"""
        self.logger: logging.Logger = make_slack_logger()
        self.reddit: praw.Reddit = reddit
        self.subreddit: praw.models.Subreddit = self.reddit.subreddit(subreddit)
        self.config: ConfigParser = ConfigParser(allow_no_value=True)
        self.config.read_string(
            self.subreddit.wiki["flairbot/config"].content_md
        )
        self.flairs: ConfigParser = ConfigParser()
        self.flairs.read_string(
            self.subreddit.wiki["flairbot/config/flairs"].content_md
        )
        self.logger.info("Flairbot initalized successfully")

    def fetch_pms(self) -> None:
        """Get PMs for account"""
        import re

        import prawcore

        try:
            for msg in self.reddit.inbox.unread():
                author: str = str(msg.author)
                valid_user: Match[str] = re.match(r"[A-Za-z0-9_-]+", author)
                if msg.subject == self.config["messages"]["subject"] and valid_user:
                    self.logger.debug("Processing request for /u/%s", author)
                    self.process_pm(msg)
        except prawcore.exceptions.RequestException:
            self.logger.exception("Request error: Sleeping for 10 seconds.")
            import time
            time.sleep(10)

    def process_pm(self, msg: praw.models.Message) -> None:
        """Process the PMs"""
        result: Optional[Tuple[str, str, str]] = self.get_flair(msg.body)
        msg.mark_read()
        if result is None:
            return

        self.set_flair(msg.author, result[0], result[1], result[2])

    def get_flair(self, flair: str) -> Optional[Tuple[str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """
        try:
            section: str = next(
                (section for section in self.flairs.sections()
                 if flair in self.flairs.options(section))
            )
        except StopIteration:
            self.logger.warning("Section is none on valid request of %s", flair)
            return None

        text: str = self.flairs[section][flair]
        return (section, flair, text)

    def set_flair(self, user: praw.models.Redditor, section: str, flair: str, text: str):
        """Set the flairs"""

        text_flairs: FrozenSet[str] = frozenset(
            self.config["types"]
        )

        for current_user_flair in self.subreddit.flair(redditor=user):
            current_class: Optional[str] = current_user_flair["flair_css_class"]
            decomposed_class: List[str] = [] if current_class is None else current_class.split(' ')
            current_text: str = current_user_flair["flair_text"]

            new_class: List[str] = []

            special: bool = False
            for text_flair in text_flairs:
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
