"""Set user flairs."""
from configparser import ConfigParser
import logging
from typing import Optional, Tuple, List

import praw
from slack_python_logging import slack_logger

class Flairbot(object):
    """Main class"""

    def __init__(self, reddit: praw.Reddit, subreddit: str) -> None:
        """Initial setup"""
        self.logger: logging.Logger = slack_logger.initialize("flairbot")
        self.reddit: praw.Reddit = reddit
        self.subreddit: praw.models.Subreddit = self.reddit.subreddit(subreddit)
        self.config: ConfigParser = self.get_config()
        self.image_flairs: ConfigParser = self.get_config("flair")
        self.text_flairs: ConfigParser = self.get_config("text")
        self.logger.info("Initalized successfully")
        return

    def get_config(self, section: Optional[str] = None) -> ConfigParser:
        """returns config"""
        self.logger.debug("Creating config")
        parser: ConfigParser = ConfigParser(allow_no_value=True)

        self.logger.debug("Getting config")
        config_location = '/'.join(item for item in ["flairbot", "config", section] if item)
        config_str: str = self.subreddit.wiki[config_location].content_md
        if config_str:
            self.logger.debug("Got config \"%s\"", config_location)
            parser.read_string(config_str)
        else:
            self.logger.error("Config \"%s\" found", config_location)

        self.logger.debug("Config created")
        return parser

    def fetch_pms(self) -> None:
        """Get PMs for account"""
        import prawcore

        try:
            for message in self.reddit.inbox.unread():
                if message.subject == self.config.get(
                        "messages",
                        "subject",
                        fallback="updateflair"
                    ):
                    self.logger.debug(
                        "Processing request \"%s\" for /u/%s",
                        message.body,
                        message.author
                    )
                    self.process_pm(message)
        except prawcore.exceptions.RequestException:
            self.logger.exception("Request error: Sleeping for 5 minutes.")
            import time
            time.sleep(60 * 5)

    def process_pm(self, message: praw.models.Message) -> None:
        """Process the PMs"""
        self.logger.debug("Updating flairs")
        self.image_flairs = self.get_config("flairs")
        self.logger.debug("Updated flairs")

        flair: str = message.body
        result: Optional[Tuple[str, str, str]] = self.get_image_flair_properties(flair)
        message.mark_read()
        if result is None:
            self.send_pm_failure(message)
            return

        self.set_flair(message.author, result[0], result[1], result[2])

    def get_image_flair_properties(self, flair: str) -> Optional[Tuple[str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """
        self.logger.debug("Getting flair properties")
        try:
            section: str = next((
                section for section in self.image_flairs.sections()
                if flair in self.image_flairs.options(section)
            ))
        except StopIteration:
            self.logger.warning("Flair \"%s\" does not exist", flair)
            return None

        default_text: str = self.image_flairs[section][flair]
        self.logger.debug("Got flair properties")
        return (section, flair, default_text)

    # pylint: disable=R0201
    def send_pm_failure(self, message: praw.models.Message):
        """pms user informing flair selection is invalid"""
        user: praw.models.Redditor = message.author

        self.logger.debug("Sending PM to /u/%s", user)
        message_str: str = (
            f"Your flair selection \"{message.body}\" was invalid."
            " Flairs can be found on the sidebar."
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
            current_class: Optional[str] = current_user_flair["flair_css_class"]
            decomposed_class: List[str] = [] if current_class is None else current_class.split(' ')
            current_text: str = current_user_flair["flair_text"]

            self.logger.debug("Setting flair for /u/%s with class \"%s\"", user, current_class)
            new_class: List[str] = []

            special: bool = False
            for role in self.text_flairs.options("roles"):
                if role in decomposed_class:
                    special = True
                    flair_color: str = self.text_flairs["roles"][role]
                    new_class.extend([role, flair_color, "text"])

            for special_role in self.text_flairs.options("special_roles"):
                if special_role in decomposed_class:
                    special = True
                    distinguished_class: str = self.text_flairs["special_roles"][special_role]
                    new_class.extend([special_role, distinguished_class])
                    special_category: str = f"{special_role}_roles"
                    for sub_role in self.text_flairs.options(special_category):
                        if sub_role in decomposed_class:
                            distinguished_color: str = self.text_flairs[special_category][sub_role]
                            new_class.extend([sub_role, distinguished_color, "text"])

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
