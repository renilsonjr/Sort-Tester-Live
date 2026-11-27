"""What the game does by the clock, with no background timer.

Nothing in this server wakes up on its own. A season still has to close
when its time is up, a tie-break round at its own deadline, and the three
hats have to be settled once the rounds are done. So every request made
behind an account first does whatever has come due, in this order, and
then goes on to its own work. When nothing is due this is a few reads.

The order is the rule, which is why it is written once here and not in
the HTTP layer: a round cannot be closed for a season that has not
finished, and prizes cannot be final while a round is still open.
"""
from backend.ranked import season_close, seasons, tiebreaks


def run(conn, *, clock, bank) -> None:
    # finish any season whose five-minute finishing window is over: end
    # unfinished attempts, settle, freeze
    season_close.finish_due_seasons(conn, clock=clock)
    # a tie-break round closes at its own deadline the same way: score it,
    # place its players, open the next round if one is due
    tiebreaks.close_due_rounds(conn, clock=clock, bank=bank)
    # once rounds are closed, resolve the three hats: carry a freed hat
    # down to the next player, open a replacement round if that creates
    # a tie, and write the winners when nothing is left pending
    launch = seasons.official_launch(conn)
    if launch is not None:
        tiebreaks.finalize_prizes(conn, launch.season_id, clock=clock, bank=bank)
