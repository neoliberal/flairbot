"""Set user flairs."""
from configparser import ConfigParser
from typing import Match, Optional, Tuple, FrozenSet, List

import praw

from slackbot.python_logging.slack_logger import make_slack_logger

class Flairbot(object):
    """Main class"""

    def __init__(self: Flairbot, reddit: praw.Reddit, subreddit: str, webhook_url: str) -> None:
        """Initial setup"""
        self.reddit: praw.Reddit = reddit
        self.subreddit: praw.models.Subreddit = self.reddit.subreddit(subreddit)
        self.config: ConfigParser = ConfigParser()
        self.config.read_string(
            self.subreddit.wiki["flairbot/config"].content_md
        )
        self.flairs: ConfigParser = ConfigParser()
        self.flairs.read_string(
            self.subreddit.wiki["flairbot/config/flairs"].content_md
        )
        self.logger = make_slack_logger(webhook_url, "Flairbot")

    def fetch_pms(self: Flairbot) -> None:
        """Get PMs for account"""
        import re

        for msg in self.reddit.inbox.unread():
            valid_user: Match[str] = re.match(r"[A-Za-z0-9_-]+", str(msg.author))
            if msg.subject == self.config["messages"]["subject"] and valid_user:
                self.process_pm(msg)

    def process_pm(self: Flairbot, msg: praw.models.Message) -> None:
        """Process the PMs"""
        msg.mark_read()

        result: Optional[Tuple[str, str, str]] = self.get_flair(msg.body)
        if result is None:
            return

        self.set_flair(msg.author, result[0], result[1], result[2])

    def get_flair(self: Flairbot, flair: str) -> Optional[Tuple[str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """

        section: Optional[str] = next(
            (section for section in self.flairs if flair in section),
            None
        )
        if section is None:
            return None
        text: str = self.flairs[section][flair]
        return (section, flair, text)

    def set_flair(self: Flairbot, user: praw.models.Redditor, section: str, flair: str, text: str):
        """Set the flairs"""

        text_flairs: FrozenSet[str] = frozenset(
            self.config["types"]
        )

        for current_user_flair in self.subreddit.flair(redditor=user):
            decomposed_class: List[str] = current_user_flair["flair_css_class"].split(' ')
            current_text: str = current_user_flair["flair_text"]

            new_class: List[str] = []

            special: bool = False
            for text_flair in text_flairs:
                if text_flair in decomposed_class:
                    special = True
                    new_class.append(text_flair)
                    break

            new_class.extend([section, flair, "image"])
            self.subreddit.flair.set(
                redditor=user,
                text=current_text if special else text,
                css_class=" ".join(new_class)
            )
