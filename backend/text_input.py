"""Rules for free text that arrives in a request.

PostgreSQL text cannot hold U+0000. A request carrying one used to reach the
database and come back as an unhandled server error, so free-text fields
refuse it up front, as bad input, like any other value that breaks a field's
rule. Nothing else is filtered here: markup and unusual characters are
stored as typed and escaped where they are drawn.
"""
from typing import Annotated

from pydantic import AfterValidator


def has_nul(text: str) -> bool:
    return "\x00" in text


def _refuse_nul(value):
    if isinstance(value, str) and has_nul(value):
        raise ValueError("text cannot contain a NUL character")
    return value


PlainText = Annotated[str, AfterValidator(_refuse_nul)]
