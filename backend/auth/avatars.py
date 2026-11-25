"""The profile icons a player may choose (issue #272).

The account stores one of these keys and nothing else: never the emoji,
never anything the player typed. So whatever reaches a screen is one of the
values this file lists, and a key that is not here is refused.

The owner approved an all-animal set on 2026-11-22 and added ten more on
2026-11-25 (ten in all). Animals keep the row even: they are full-colour glyphs of
similar weight on every phone, while symbols like a star or a bolt render
flat and smaller next to them. None of them reads as a person or as a
company mark.

New keys go at the end. The order is what the picker draws, so inserting in
the middle would move every icon under somebody's finger for no reason.

The emoji themselves live in ``src/avatars.js``, because drawing is the
screen's job; ``tests/avatar-list.test.mjs`` holds the two lists to the same
keys in the same order.
"""

KEYS = (
    "fox",
    "panda",
    "lion",
    "frog",
    "owl",
    "octopus",
    "bee",
    "dinosaur",
    "turtle",
    "butterfly",
    "penguin",
    "deer",
    "fish",
    "raccoon",
    "caterpillar",
    # added 2026-11-25
    "pig",
    "rabbit",
    "dog",
    "hedgehog",
    "squirrel",
    "cat",
    "bear",
    "unicorn",
    "tabby",
    "giraffe",
)


def is_allowed(key) -> bool:
    """Whether ``key`` is one of the approved set. Anything else is False.

    Not case-insensitive and not trimmed on purpose: the screen sends a key
    it was given, so anything that needs tidying up did not come from there.
    """
    return isinstance(key, str) and key in KEYS
