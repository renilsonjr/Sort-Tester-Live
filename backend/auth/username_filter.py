"""Refuse offensive usernames (issue #515, owner decision 2026-11-28).

A username is already limited to 3-24 letters, digits and underscores.
This adds a check of what it says: racist, hateful or profane words in
English or Spanish are refused, including look-alike spellings such as
digits for letters, underscores between letters and repeated letters.

The word lists are in ``backend.auth.blocked_names``. Every check is done
on the server; the app only shows the refusal.
"""
import re

from backend.auth import blocked_names

# Digits and the one symbol a username may hold, read as the letters they
# usually stand in for. "1" is read both ways, as "i" and as "l".
_LOOK_ALIKE = str.maketrans({"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g"})
_HATE_NUMBERS = ("1488",)


def _readings(text: str) -> set[str]:
    """The ways a run of characters can be read once digits stand for letters."""
    base = text.translate(_LOOK_ALIKE)
    return {base.replace("1", "i"), base.replace("1", "l")}


def _squeeze(text: str) -> str:
    """Collapse repeated letters: a name can stretch a word to dodge a list."""
    return re.sub(r"(.)\1+", r"\1", text)


def _forms(text: str) -> set[str]:
    """The letters-only readings of a name, as written."""
    return {re.sub(r"[^a-z]", "", reading) for reading in _readings(text)}


# With repeats collapsed on both sides, so "biiig" meets "big" and a word
# that is spelled with a double letter still meets itself. Only words of
# four letters or more once collapsed: a collapsed short word ("as") would
# turn up inside ordinary names.
_MIN_SQUEEZED = 4
_ANYWHERE_SQ = frozenset(
    s for s in map(_squeeze, blocked_names.ANYWHERE) if len(s) >= _MIN_SQUEEZED
)
_WHOLE_WORD_SQ = frozenset(
    s for s in map(_squeeze, blocked_names.WHOLE_WORD) if len(s) >= _MIN_SQUEEZED
)


def _hits(forms: set[str], anywhere: bool) -> bool:
    for form in forms:
        squeezed = _squeeze(form)
        if form in blocked_names.WHOLE_WORD or squeezed in _WHOLE_WORD_SQ:
            return True
        if anywhere and (
            any(word in form for word in blocked_names.ANYWHERE)
            or any(word in squeezed for word in _ANYWHERE_SQ)
        ):
            return True
    return False


def is_blocked(username: str) -> bool:
    """True when the username contains a blocked word, however it is spelled."""
    name = (username or "").strip().lower()
    if not name:
        return False
    if any(number in name for number in _HATE_NUMBERS):
        return True

    whole = _forms(name)
    if whole & blocked_names.ALLOW:
        return False

    # Anywhere in the name, with underscores and stray digits gone.
    if _hits(whole, anywhere=True):
        return True

    # As one whole part of the name: "_" separates parts, and digits at
    # either end of a part are a number, not a letter ("ass123").
    for part in name.split("_"):
        trimmed = part.strip("0123456789")
        for candidate in {part, trimmed}:
            if candidate and _hits(_forms(candidate), anywhere=False):
                return True
    return False
