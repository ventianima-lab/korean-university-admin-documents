#!/usr/bin/env python3
"""Fail-closed comparison of verified, final per-item payable totals in won."""
import argparse
import re
import sys


def positive_won(value):
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise argparse.ArgumentTypeError("enter a confirmed positive whole-won total")
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-total", required=True, type=positive_won)
    parser.add_argument("--candidate-total", required=True, type=positive_won)
    args = parser.parse_args(argv)
    if args.candidate_total <= args.main_total:
        print("INELIGIBLE: candidate final total must exceed the main final total")
        return 1
    print("PRICE_GATE_PASSED: verify the original evidence and all other conditions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
