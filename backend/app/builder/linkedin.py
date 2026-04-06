"""LinkedIn URL detection utility for the AI Scenario Builder."""

import re

_LINKEDIN_PATTERN = re.compile(r"https://www\.linkedin\.com/in/.+")


def is_linkedin_url(text: str) -> bool:
    """Return True if *text* contains a LinkedIn profile URL.

    Matches the pattern ``https://www.linkedin.com/in/<anything>`` anywhere
    in the input string.
    """
    return bool(_LINKEDIN_PATTERN.search(text))
