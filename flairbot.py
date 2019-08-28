"""Set user flairs."""
from configparser import ConfigParser, ParsingError
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
        self.config: ConfigParser = self.get_wiki_page()
        self.logger.info("Initalized successfully")
        return

    def get_wiki_page(self, page: Optional[str] = None) -> ConfigParser:
        """gets current groups"""
        groups: ConfigParser = ConfigParser(allow_no_value=True)

        combined_page: str = '/'.join(filter(None, ["flairbot", "config", page]))
        self.logger.debug("Getting wiki page \"%s\"", combined_page)
        import prawcore
        try:
            groups.read_string(self.subreddit.wiki[combined_page].content_md)
        except prawcore.exceptions.NotFound:
            self.logger.error("Could not find wiki page %s", combined_page)
            raise
        except ParsingError:
            self.logger.exception("Malformed file, could not parse")
            raise
        except prawcore.exceptions.PrawcoreException:
            self.logger.exception("Unknown exception caught")
            raise
        self.logger.debug("Successfully got groups")
        return groups

    def fetch_pms(self) -> None:
        """Get PMs for account"""
        import prawcore
        from time import sleep
        try:
            for message in self.reddit.inbox.unread():
                if message.subject == self.config.get(
                        "messages", "subject", fallback="updateflair"):
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

            if 'brown' in current_class:
                self.send_pm_not_allowed(message)
                return

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

            # As far as I can tell, the default text is always applied
            # If that ISN'T true, then stuff might break here
            # Prepend emoji to flair text
            text = f":{image_flair[1]}: {text}"

            combined_class: str = " ".join(new_class)
            self.subreddit.flair.set(redditor=author, text=text, css_class=combined_class)
            self.logger.debug("/u/%s changed to \"%s\" (%s)", author, text, combined_class)

    def image_flair_properties(self, image_flair: str) -> Optional[Tuple[str, str, str, str]]:
        """
        Match flair selection to correct category

        returns None if no match
        """
        self.logger.debug("Updating image flairs")
        image_flairs: ConfigParser = self.get_wiki_page("images")
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
        text_flairs: ConfigParser = self.get_wiki_page("text")
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

    def send_pm_not_allowed(self, message: praw.models.Message):
        """PMs user that they're not allowed to change their flair"""
        user: praw.models.Redditor = message.author
        flair: str = message.body
        self.logger.debug("Sending PM to /u/%s", user)
        message_str: str = ("You have a brown shame flair, and therefore are not allowed to change it.")
        user.message(subject="Flair update failed", message=message_str)
        self.logger.debug("PM sent to /u/%s", user)
        return
