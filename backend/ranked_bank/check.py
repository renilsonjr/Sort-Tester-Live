"""Read-only, answer-free developer check of a reviewed Ranked assignment."""
import argparse
from collections import Counter
import json
from random import Random
import sys
from typing import Sequence

from .catalog import load_reviewed_bank
from .models import BankUnavailableError, BankValidationError
from .selection import select_assignment


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='ranked-routes-v1')
    parser.add_argument('--seed', type=int)
    args = parser.parse_args(argv)
    try:
        bank = load_reviewed_bank(args.revision)
        snapshot = select_assignment(bank, rng=None if args.seed is None else Random(args.seed))
    except (BankValidationError, BankUnavailableError) as exc:
        print(f'{exc.code}: {exc}', file=sys.stderr)
        return 1
    result = dict(bank_revision=snapshot.bank_revision, bank_sha256=snapshot.bank_sha256,
                  question_count=len(snapshot.questions), counts=dict(Counter(q.difficulty for q in snapshot.questions)),
                  selected_review_refs=[q.source.review_ref for q in snapshot.questions])
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
