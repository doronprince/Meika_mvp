"""Measure the exposure-vs-spending test's power and false-positive rate.

Honest scope: SYNTHETIC users with a known ground truth. This shows how the
statistical test behaves (does it find an effect that is really there? does
it invent one that isn't?), not how people behave.

Every synthetic user has 84 days of logged screen time and discretionary
spending that BOTH rise on weekends — the confound the weekday demeaning is
there to remove. Cohorts:

  null:    exposure and spending are otherwise independent.
  effect:  after a day with 60+ minutes of exposure, an extra impulse
           purchase happens the same or next day with probability `--effect`.

Reported for the shipped method (weekday-demeaned) and, as an ablation, for
the same test WITHOUT demeaning: the false-positive rate is the share of
null users flagged, and power is the share of effect users flagged.

Usage:
    cd backend
    python -m scripts.eval_exposure [--users 200] [--seed 5] [--effect 0.6]
"""

import argparse
import random
from datetime import date, timedelta

from app.services.exposure_service import SIGNIFICANCE_LEVEL, association

DAYS = 84
START = date(2026, 6, 1)


def make_user(rng: random.Random, effect_p: float) -> tuple[list[float], list[float], list[date]]:
    days = [START + timedelta(days=i) for i in range(DAYS)]
    weekend_boost = rng.uniform(0.3, 0.8)
    exposure, spend = [], [0.0] * DAYS
    for i, day in enumerate(days):
        weekend = day.weekday() >= 5
        p_scroll = 0.45 + (weekend_boost if weekend else 0) * 0.5
        minutes = rng.choice([15, 30, 45, 60, 90, 120]) if rng.random() < p_scroll else 0
        exposure.append(float(minutes))
        if rng.random() < (0.35 + (0.3 if weekend else 0)):
            spend[i] += rng.uniform(4_000, 25_000)
        if effect_p and minutes >= 60 and rng.random() < effect_p:
            target = min(DAYS - 1, i + rng.choice([0, 1]))
            spend[target] += rng.uniform(20_000, 60_000)
    return exposure, spend, days


def flagged(exposure: list[float], spend: list[float], days: list[date], *, demean: bool) -> bool:
    pair_days = days[:-1]
    window = [spend[i] + spend[i + 1] for i in range(len(days) - 1)]
    result = association(exposure[:-1], pair_days, window, pair_days, demean=demean)
    return (
        result.spearman_rho is not None
        and result.p_value is not None
        and result.spearman_rho > 0
        and result.p_value < SIGNIFICANCE_LEVEL
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--effect", type=float, default=0.6, help="chance of an extra impulse purchase after 60+ min")
    args = parser.parse_args()
    rng = random.Random(args.seed)

    null_users = [make_user(rng, 0.0) for _ in range(args.users)]
    effect_users = [make_user(rng, args.effect) for _ in range(args.users)]

    print(f"Synthetic: {args.users} null + {args.users} effect users, {DAYS} days each, weekend confound in all, "
          f"effect probability {args.effect}, seed {args.seed}, alpha {SIGNIFICANCE_LEVEL}.\n")
    print("| method | false-positive rate (null) | power (effect) |")
    print("|---|---|---|")
    for demean, name in ((True, "weekday-demeaned (shipped)"), (False, "raw, no demeaning (ablation)")):
        fp = sum(flagged(*u, demean=demean) for u in null_users) / len(null_users)
        power = sum(flagged(*u, demean=demean) for u in effect_users) / len(effect_users)
        print(f"| {name} | {fp:.0%} | {power:.0%} |")


if __name__ == "__main__":
    main()
