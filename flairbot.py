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
        self.image_flairs: ConfigParser = self.get_config("images")
        self.text_flairs: ConfigParser = self.get_config("text")
        self.logger.info("Initalized successfully")
        return

    def get_config(self, section: Optional[str] = None) -> ConfigParser:
        """returns config"""
        self.logger.debug("Creating config")
        parser: ConfigParser = ConfigParser(allow_no_value=True)

        self.logger.debug("Getting config")
        config_location = '/'.join(item for item in ["flairbot", "config", section] if item)
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
                    self.logger.debug(
                        "Processing request \"%s\" for /u/%s",
                        message.body,
                        message.author
                    )
                    self.process_pm(message)
        except prawcore.exceptions.RequestException:
            self.logger.debug("Request error: Sleeping for 5 minutes.")
            sleep(60 * 5)
        except prawcore.exceptions.ResponseException:
            self.logger.error("Response error: Sleeping for 1 minute.")
            sleep(60)

    def process_pm(self, message: praw.models.Message) -> None:
        """Process the PMs"""
        self.logger.debug("Updating image and text flairs")
        self.image_flairs = self.get_config("images")
        self.text_flairs = self.get_config("text")
        self.logger.debug("Updated flairs")

        result: Optional[Tuple[str, str, str]] = self.get_image_flair_properties(message.body)
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
            return None

        default_text: str = self.image_flairs[section][flair]
        self.logger.debug("Got flair properties")
        return (section, flair, default_text)

    # pylint: disable=R0201
    def send_pm_failure(self, message: praw.models.Message):
        """pms user informing flair selection is invalid"""
        user: praw.models.Redditor = message.author
        flair: str = message.body
        self.logger.warning("Flair selection \"%s\" by /u/%s does not exist", flair, str(user))

        self.logger.debug("Sending PM to /u/%s", user)
        message_str: str = (
            f"Your flair selection \"{flair}\" was invalid."
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

            self.logger.debug("Setting flair for /u/%s with class \"%s\"", user, current_class)
            new_class: List[str] = []

            special: bool = False
            for role, flair_color in self.text_flairs.items("roles"):
                if role in decomposed_class:
                    special = True
                    new_class.extend([role, flair_color, "text"])

            for special_role, distinguished_class in self.text_flairs.items("special_roles"):
                if special_role in decomposed_class:
                    special = True
                    new_class.extend([special_role, distinguished_class])
                    for sub_role, flair_color in self.text_flairs.items(f"{special_role}_roles"):
                        if sub_role in decomposed_class:
                            new_class.extend([sub_role, flair_color, "text"])

            new_class.extend([section, flair, "image"])
            new_text: str = current_user_flair["flair_text"] if special else text
            combined_class: str = " ".join(new_class)
            self.subreddit.flair.set(
                redditor=user,
                text=new_text,
                css_class=combined_class
            )
            self.logger.debug("Flair for /u/%s changed to \"%s\" (%s)",
                              user, new_text, combined_class
                             )
