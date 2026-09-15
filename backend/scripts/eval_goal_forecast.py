"""Measures goal forecasting instead of asserting it works.

    python -m scripts.eval_goal_forecast            # table to stdout
    python -m scripts.eval_goal_forecast --json out.json

Backtests app.services.goal_forecast.forecast_goal (the production function,
not a re-implementation) on seeded synthetic savings ledgers, against two
named baselines, at several points in each goal's life:

- no_further_progress — final = what's saved so far. The "do nothing
  clever" floor.
- recent_7_day_pace   — projects only the last 7 days' pace forward. The
  obvious competitor: reacts faster to a change in behaviour, noisier.
- meika_average_pace  — the shipped model: average pace since start.

Point-in-time protocol: a forecast at day d sees only contributions on days
1..d. Metrics:
- MAE of the projected final amount, as % of target.
- Outcome accuracy: did "projected >= target" match what really happened?

HONEST LIMITS, printed with the results: these ledgers are synthetic
behaviour profiles, not real users, so the numbers show how the model
behaves under known dynamics (steady, stalling, ramping, lumpy, decaying) —
including where it loses to the baseline — not how accurate it is in the
wild. Replacing SYNTHETIC with anonymised real ledgers is the next step.
"""

import argparse
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.models.enums import GoalType
from app.services.currency_display import DisplayCurrency
from app.services.goal_forecast import forecast_goal

SEED = 42
LEDGERS_PER_PROFILE = 200
DAYS = 60
CHECKPOINTS = (7, 14, 21, 30, 45)
BASE_DAILY = 10_000.0
START = date(2026, 1, 1)
KRW = DisplayCurrency("KRW", Decimal("1"))


def _steady(rng: random.Random, day: int) -> float:
    return BASE_DAILY * rng.uniform(0.8, 1.2)


def _stall(rng: random.Random, day: int) -> float:
    # Normal saving for the first 40% of the window, then it nearly stops.
    return BASE_DAILY * rng.uniform(0.8, 1.2) * (1.0 if day <= DAYS * 0.4 else 0.1)


def _ramp(rng: random.Random, day: int) -> float:
    return BASE_DAILY * (0.5 + day / DAYS) * rng.uniform(0.8, 1.2)


def _lumpy(rng: random.Random, day: int) -> float:
    # A weekly transfer that is sometimes skipped.
    return BASE_DAILY * 7 if day % 7 == 0 and rng.random() > 0.2 else 0.0


def _decay(rng: random.Random, day: int) -> float:
    return BASE_DAILY * (1.5 - day / DAYS) * rng.uniform(0.8, 1.2)


PROFILES = {"steady": _steady, "stall": _stall, "ramp": _ramp, "lumpy": _lumpy, "decay": _decay}
METHODS = ("no_further_progress", "recent_7_day_pace", "meika_average_pace")


@dataclass
class Ledger:
    profile: str
    daily: list[float]  # index 0 = day 1
    target: float

    @property
    def final(self) -> float:
        return sum(self.daily)


def build_ledgers(rng: random.Random) -> list[Ledger]:
    ledgers = []
    for name, generator in PROFILES.items():
        for _ in range(LEDGERS_PER_PROFILE):
            daily = [generator(rng, day) for day in range(1, DAYS + 1)]
            # Targets around the nominal total, so roughly half the goals are met.
            target = BASE_DAILY * DAYS * rng.uniform(0.8, 1.2)
            ledgers.append(Ledger(name, daily, target))
    return ledgers


def project(method: str, ledger: Ledger, day: int) -> float:
    so_far = sum(ledger.daily[:day])
    remaining = DAYS - day
    if method == "no_further_progress":
        return so_far
    if method == "recent_7_day_pace":
        window = ledger.daily[max(0, day - 7):day]
        return so_far + sum(window) / len(window) * remaining
    forecast = forecast_goal(
        goal_type=GoalType.SAVINGS,
        target_krw=Decimal(str(round(ledger.target, 2))),
        start_date=START,
        target_date=START + timedelta(days=DAYS - 1),
        today=START + timedelta(days=day - 1),
        progress_krw=Decimal(str(round(so_far, 2))),
        display=KRW,
    )
    if forecast.projected_final_krw is None:
        # Already achieved: the production model stops projecting, final >= target.
        return so_far
    return float(forecast.projected_final_krw)


def evaluate(ledgers: list[Ledger]) -> dict:
    results: dict = {}
    for day in CHECKPOINTS:
        for profile in (*PROFILES, "all"):
            subset = [lg for lg in ledgers if profile in ("all", lg.profile)]
            row = {}
            for method in METHODS:
                abs_errors, correct = [], 0
                for ledger in subset:
                    projected = project(method, ledger, day)
                    abs_errors.append(abs(projected - ledger.final) / ledger.target * 100)
                    correct += (projected >= ledger.target) == (ledger.final >= ledger.target)
                row[method] = {
                    "mae_pct_of_target": round(sum(abs_errors) / len(abs_errors), 2),
                    "outcome_accuracy_pct": round(correct / len(subset) * 100, 1),
                }
            results.setdefault(f"day_{day}", {})[profile] = row
    return results


def print_table(results: dict, ledgers: list[Ledger]) -> None:
    met = sum(lg.final >= lg.target for lg in ledgers) / len(ledgers) * 100
    print(f"Goal forecast backtest — {len(ledgers)} synthetic {DAYS}-day savings ledgers, seed {SEED}")
    print(f"Base rate: {met:.1f}% of goals are actually met.\n")
    short = {"no_further_progress": "no-progress", "recent_7_day_pace": "recent-7d", "meika_average_pace": "meika"}
    for checkpoint, by_profile in results.items():
        print(f"== {checkpoint.replace('_', ' ')} of {DAYS} ==")
        print(f"{'profile':<8} | {'MAE % of target':^36} | {'outcome accuracy %':^36}")
        print(f"{'':<8} | " + " ".join(f"{short[m]:>11}" for m in METHODS) + "  | "
              + " ".join(f"{short[m]:>11}" for m in METHODS))
        for profile, row in by_profile.items():
            maes = " ".join(f"{row[m]['mae_pct_of_target']:>11.2f}" for m in METHODS)
            accs = " ".join(f"{row[m]['outcome_accuracy_pct']:>11.1f}" for m in METHODS)
            print(f"{profile:<8} | {maes}  | {accs}")
        print()
    print("Limits: synthetic behaviour profiles, not real users. Read per-profile rows for where the average-pace")
    print("model loses (stall / decay favour a recent-window pace), not just the 'all' row.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="also write results to this path")
    args = parser.parse_args()

    ledgers = build_ledgers(random.Random(SEED))
    results = evaluate(ledgers)
    print_table(results, ledgers)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"seed": SEED, "ledgers": len(ledgers), "days": DAYS, "results": results}, fh, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
