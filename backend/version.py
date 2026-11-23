"""The app's version number (issue #274).

One string, in one place. Everything that reports a version reads it from
here: ``/health`` serves it, and the Profile screen asks ``/health`` rather
than drawing a number of its own, so what a player sees is the version
actually running and not the one that happened to be in the file when their
page was built.

**The suffix is not decoration.** ``-dev`` means "this is being prepared,
and no tag exists for it yet". The owner decided on 2026-11-23 to cut
``v0.1.0`` only once issue #273 is finished, so until that tag exists this
must not claim to be ``0.1.0``.

Cutting a release is three things that have to agree, and this file is the
first of them:

1. this string, with the suffix removed;
2. the git tag ``v<version>`` on the commit that carries it;
3. the image digest published from that commit, recorded in
   ``infra/azure/releases.md`` together with the migration it needs.

What the numbers mean (owner's rule, #274):

* **patch** (0.1.0 -> 0.1.1): a fix. Nothing new to learn, nothing moved.
* **minor** (0.1 -> 0.2): something new, or a screen that works differently.
* **major** (0.x -> 1.0): reserved for when the app is past its pilot.
"""

VERSION = "0.1.0-dev"
