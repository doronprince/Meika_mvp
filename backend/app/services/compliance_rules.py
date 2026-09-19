"""Loads the tax & compliance ruleset from app/data/compliance_rules.json.

[[compliance-rules-are-data]]: everything about a rule — what it matches,
its window, its assumed figure and the wording that goes with it — lives in
that JSON file. Changing a rule is a reviewable diff with an author and a
date, and no detector contains a rule-specific branch.

[[frozen-threshold-rate]]: a figure that started life in another currency
(e.g. USD 10,000) is stored as a frozen KRW amount with the rate and the
rate's date recorded beside it. It is never re-derived from live FX: a
threshold that moved every day would make the same ledger flag on Tuesday
and not on Wednesday for no reason the user did anything about.

A rule that fails validation is excluded and reported (reason
rule_spec_invalid), never raised: the other rules still run.
"""

import functools
import json
import pathlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.models.enums import ExpenseCategory
from app.schemas.common import RiskLevel
from app.schemas.compliance import ComplianceDetectorKind

RULES_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "compliance_rules.json"

# Rule regexes are author-controlled, never user input, but they still run
# against every logged title — kept short, and tested for catastrophic
# backtracking in tests/test_compliance_detectors.py.
MAX_REGEX_LENGTH = 200

_THRESHOLD_KINDS = {ComplianceDetectorKind.THRESHOLD_ACCUMULATION, ComplianceDetectorKind.SINGLE_LINE_THRESHOLD}


class RuleMatch(BaseModel):
    categories: list[ExpenseCategory] | None = None
    currency_mode: Literal["any", "foreign_only", "krw_only"] = "any"
    min_amount_krw: Decimal | None = None
    text_regex: str | None = Field(default=None, max_length=MAX_REGEX_LENGTH)

    @model_validator(mode="after")
    def _regex_compiles(self):
        if self.text_regex:
            re.compile(self.text_regex, re.IGNORECASE)
        return self


class ThresholdBasis(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    krw_per_unit: Decimal = Field(gt=0)
    rate_as_of: date


class RuleThreshold(BaseModel):
    amount_krw: Decimal = Field(gt=0)
    basis: ThresholdBasis | None = None

    @model_validator(mode="after")
    def _basis_consistent(self):
        if self.basis and self.basis.amount * self.basis.krw_per_unit != self.amount_krw:
            raise ValueError("amount_krw must equal basis.amount x basis.krw_per_unit")
        return self


class ComplianceRuleSpec(BaseModel):
    rule_key: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    detector_kind: ComplianceDetectorKind
    title: str
    question: str
    amount_basis: Literal["amount_only", "amount_plus_transit"] = "amount_only"
    match: RuleMatch = Field(default_factory=RuleMatch)
    match_description: str
    params: dict[str, Any] = Field(default_factory=dict)
    threshold: RuleThreshold | None = None
    assumption_statement: str
    verification_prompt: str
    source_note: str
    max_severity: RiskLevel

    @model_validator(mode="after")
    def _threshold_present_when_needed(self):
        if self.detector_kind in _THRESHOLD_KINDS and self.threshold is None:
            raise ValueError(f"{self.detector_kind.value} rules need a threshold")
        return self

    @property
    def basis_note(self) -> str | None:
        basis = self.threshold.basis if self.threshold else None
        if basis is None:
            return None
        return (
            f"{basis.currency} {basis.amount:,} held at a frozen {basis.krw_per_unit:,} KRW/{basis.currency} "
            f"as of {basis.rate_as_of.isoformat()}"
        )


@dataclass(frozen=True)
class InvalidRule:
    rule_key: str
    title: str
    error: str


@dataclass(frozen=True)
class Ruleset:
    version: str
    rules: tuple[ComplianceRuleSpec, ...]
    invalid: tuple[InvalidRule, ...]

    def get(self, rule_key: str) -> ComplianceRuleSpec | None:
        return next((r for r in self.rules if r.rule_key == rule_key), None)


def parse_ruleset(raw: dict) -> Ruleset:
    rules: list[ComplianceRuleSpec] = []
    invalid: list[InvalidRule] = []
    for entry in raw.get("rules", []):
        try:
            rules.append(ComplianceRuleSpec.model_validate(entry))
        except ValidationError as exc:
            invalid.append(
                InvalidRule(
                    rule_key=str(entry.get("rule_key", "unknown")),
                    title=str(entry.get("title", entry.get("rule_key", "Unknown rule"))),
                    error="; ".join(err["msg"] for err in exc.errors()),
                )
            )
    return Ruleset(version=str(raw.get("version", "unversioned")), rules=tuple(rules), invalid=tuple(invalid))


@functools.lru_cache(maxsize=4)
def load_ruleset(path: pathlib.Path = RULES_PATH) -> Ruleset:
    return parse_ruleset(json.loads(path.read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=64)
def compiled_regex(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)
