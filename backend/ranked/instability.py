"""The connection instability counting rule (issue #25).

Decides, from one attempt's connection events, whether it contains a run of
losses that qualifies for a private review flag. Pure arithmetic: no database.

The rule is the owner's (decision record, Decision 7): count distinct losses
after recovery; duplicates for one uninterrupted loss count once; four losses
qualify when each consecutive gap is under five seconds; a gap of exactly five
seconds or more starts a new sequence.

A flag is an instability signal for a human reviewer, never proof of cheating.
Nothing here, or built on it, changes points or access.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

RUN_LENGTH = 4
MAX_GAP_SECONDS = 5

# events at the same instant are read in this order
_ORDER = {"loss": 0, "recovery": 1, "expiry": 2}


@dataclass(frozen=True)
class Run:
    first_loss_at: datetime
    last_loss_at: datetime  # the loss that completed the run


def distinct_losses(events) -> list[datetime]:
    """Loss instants in time order, one per uninterrupted interruption.

    ``events`` are ``(kind, occurred_at)`` pairs as the attempt engine writes
    them. A loss with no recovery since the previous loss is the same
    interruption and is not counted again.
    """
    losses = []
    interrupted = False
    for kind, occurred_at in sorted(events, key=_sort_key):
        if kind == "loss":
            if not interrupted:
                losses.append(occurred_at)
                interrupted = True
        elif kind == "recovery":
            interrupted = False
        # an expiry ends the attempt; it neither adds a loss nor a recovery
    return losses


def qualifying_run(events) -> Run | None:
    """The first run of four distinct losses whose every consecutive gap is
    under five seconds, or ``None``. A gap of five seconds or more ends the
    current run; the later loss starts a new one."""
    max_gap = timedelta(seconds=MAX_GAP_SECONDS)
    run = []
    for loss_at in distinct_losses(events):
        if run and loss_at - run[-1] >= max_gap:
            run = []
        run.append(loss_at)
        if len(run) == RUN_LENGTH:
            return Run(first_loss_at=run[0], last_loss_at=run[-1])
    return None


def _sort_key(event):
    kind, occurred_at = event
    if kind not in _ORDER:
        raise ValueError(f"unknown connection event kind: {kind!r}")
    return (occurred_at, _ORDER[kind])
