"""Set user flairs."""
from configparser import ConfigParser
import logging
from typing import Optional, Tuple, List

import praw
from slack_python_logging import slack_logger

class Flairbot(object):
    """Main class"""
    __slots__ = ["reddit", "subreddit", "config", "logger"]

    def __init__(self, reddit: praw.Reddit, subreddit: str) -> None:
        """Initial setup"""
        self.logger: logging.Logger = slack_logger.initialize("flairbot")
        self.reddit: praw.Reddit = reddit
        self.subreddit: praw.models.Subreddit = self.reddit.subreddit(subreddit)
        self.config: ConfigParser = self.get_config()
        self.logger.info("Initalized successfully")
        return

    def get_config(self, section: Optional[str] = None) -> ConfigParser:
        """returns config"""
        self.logger.debug("Creating config")
        parser: ConfigParser = ConfigParser(allow_no_value=True)

        self.logger.debug("Getting config")
        config_location: str = '/'.join(filter(None, ["flairbot", "config", section]))
        import prawcore
        try:
            config_str: str = self.subreddit.wiki[config_location].content_md
        except prawcore.exceptions.NotFound:
            self.logger.error("Config \"%s\" found", config_location)
        else:
            self.logger.debug("Got config \"%s\"", config_location)
            parser.read_string(config_str)

        self.logger.debug("Config created")
        return parser

    def fetch_pms(self) -> None:
        """Get PMs for account"""
        import prawcore
        from time import sleep
        try:
            for message in self.reddit.inbox.unread():
                if message.subject == self.config.get(
                        "messages",
                        "subject",
                        fallback="updateflair"
                    ):
                    message.mark_read()
                    self.set_flair(message)
        except prawcore.exceptions.ServerError:
            self.logger.error("Server error: Sleeping for 1 minute.")
            sleep(60)
        except prawcore.exceptions.RequestException:
            self.logger.debug("Request error: Sleeping for 5 minutes.")
            sleep(60 * 5)
        except prawcore.exceptions.ResponseException:
            self.logger.error("Response error: Sleeping for 1 minute.")
            sleep(60)

    def set_flair(self, message: praw.models.Message) -> None:
        """Set the flairs"""
        author: praw.models.Redditor = message.author
        for current_user_flair in self.subreddit.flair(redditor=author):
            current_class: Optional[str] = current_user_flair["flair_css_class"]
            text: str = current_user_flair["flair_text"]
            self.logger.debug("Setting flair for /u/%s with class \"%s\"", author, current_class)

            decomposed_class: List[str] = [] if current_class is None else current_class.split(' ')
            new_class: List[str] = []

            image_flair: Optional[Tuple[str, ...]] = self.image_flair_properties(message.body)
            if image_flair is None:
                self.send_pm_failure(message)
                return
            else:
                *image_properties, default_text = image_flair #type: ignore
                new_class.extend(image_properties) # type: ignore

            text_flair: Optional[Tuple[str, ...]] = self.text_flair_properties(decomposed_class)
            if text_flair is not None:
                new_class.extend(list(text_flair))
            else:
                text = default_text

            combined_class: str = " ".join(new_class)
            self.subreddit.flair.set(redditor=author, text=text, css_class=combined_class)
            self.logger.debug("/u/%s changed to \"%s\" (%s)", author, text, combined_class)

    def image_flair_properties(self, image_flair: str) -> Optional[Tuple[str, str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """
        self.logger.debug("Updating image flairs")
        image_flairs: ConfigParser = self.get_config("images")
        self.logger.debug("Updated image flairs")

        self.logger.debug("Getting image flair properties for selection")
        try:
            section: str = next((
                section for section, image_flairs in image_flairs.items()
                if image_flair in image_flairs
            ))
        except StopIteration:
            self.logger.debug("Could not find match")
            return None

        default_text: str = image_flairs[section][image_flair]
        self.logger.debug("Got flair properties")
        return (section, image_flair, "image", default_text)

    def text_flair_properties(self, old: List[str]) -> Optional[Tuple[str, ...]]:
        """
        Matches old text flair to correct category

        returns None if no math
        """
        self.logger.debug("Updating text flairs")
        text_flairs: ConfigParser = self.get_config("text")
        self.logger.debug("Updated text flairs")

        self.logger.debug("Getting text flair properties")
        for role, flair_color in text_flairs.items("roles"):
            if role in old:
                self.logger.debug("Found text flair match")
                return (role, flair_color, "text")

        for special_role, distinguished_class in text_flairs.items("special_roles"):
            if special_role in old:
                for sub_role, flair_color in text_flairs.items(f"{special_role}_roles"):
                    if sub_role in old:
                        return (special_role, distinguished_class, sub_role, flair_color, "text")
        self.logger.debug("Could not find matching text flair")
        return None

    # pylint: disable=R0201
    def send_pm_failure(self, message: praw.models.Message):
        """pms user informing flair selection is invalid"""
        user: praw.models.Redditor = message.author
        flair: str = message.body
        self.logger.warning("Flair selection \"%s\" by /u/%s does not exist", flair, str(user))

        self.logger.debug("Sending PM to /u/%s", user)
        message_str: str = (f"Your flair selection \"{flair}\" was invalid."
                            " Flairs can be found on the sidebar.")

        user.message(subject="Flair update failed", message=message_str)

        self.logger.debug("PM sent to /u/%s", user)
        return
