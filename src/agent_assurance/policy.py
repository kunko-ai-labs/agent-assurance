"""Organisation policy: tune the model without forking it.

`agent-assurance.policy.yaml` (apiVersion `agent-assurance/policy/v1`) can
override the risk weights, the band thresholds, which bands gate, which
capability and data classes break a promise, the list of read-only shell
commands, and add the organisation's own MCP servers to the catalogue.

Without a policy file every default below equals the built-in model, so
behaviour is unchanged. When a policy is active, every report names it and
carries its sha256: a verdict is only reproducible if you know which policy
produced it.

Defaults are the source of truth for the documented model; `risk.py`,
`blast_radius.py`, `declared_vs_observed.py`, `claude_settings.py` and
`catalog.py` read from `current()`.
"""

from __future__ import annotations

import hashlib
import os

import yaml
from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, model_validator

from .manifest import DataClass, ManifestError, ToolAccess

API_VERSION = "agent-assurance/policy/v1"
DEFAULT_FILE = "agent-assurance.policy.yaml"


class ToolWeights(BaseModel):
    read: NonNegativeInt = 1
    execute: NonNegativeInt = 3
    write: NonNegativeInt = 3
    external_send: NonNegativeInt = 3
    delete: NonNegativeInt = 5
    financial: NonNegativeInt = 5
    unknown: NonNegativeInt = 3

    def as_map(self) -> dict[ToolAccess, int]:
        return {ToolAccess(k): v for k, v in self.model_dump().items()}


class DataWeights(BaseModel):
    public: NonNegativeInt = 0
    internal: NonNegativeInt = 1
    pii: NonNegativeInt = 3
    health: NonNegativeInt = 4
    financial: NonNegativeInt = 4
    credential: NonNegativeInt = 5

    def as_map(self) -> dict[DataClass, int]:
        return {DataClass(k): v for k, v in self.model_dump().items()}


class Weights(BaseModel):
    tools: ToolWeights = Field(default_factory=ToolWeights)
    data: DataWeights = Field(default_factory=DataWeights)
    production: NonNegativeInt = 5
    irreversible: NonNegativeInt = 5
    delegation: NonNegativeInt = 3
    autonomy_per_level: NonNegativeInt = 2  # above L2
    auto_approval: NonNegativeInt = 2  # non-read, unscoped, no human in the loop


class Bands(BaseModel):
    """Lower bound of each band; LOW starts at 0."""

    medium: int = 8
    high: int = 16
    critical: int = 28

    @model_validator(mode="after")
    def _ascending(self) -> Bands:
        # Overlapping or reversed bounds would make a band unreachable.
        if not 0 < self.medium < self.high < self.critical:
            raise ValueError(
                f"band bounds must rise strictly: 0 < medium < high < critical "
                f"(got medium={self.medium}, high={self.high}, critical={self.critical})"
            )
        return self

    def table(self) -> list[tuple[int, str]]:
        return [(0, "LOW"), (self.medium, "MEDIUM"), (self.high, "HIGH"), (self.critical, "CRITICAL")]


BAND_ORDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class Gate(BaseModel):
    review_bands: list[str] = Field(default_factory=lambda: ["HIGH"])
    fail_bands: list[str] = Field(default_factory=lambda: ["CRITICAL"])

    @model_validator(mode="after")
    def _consistent(self) -> Gate:
        """A gate that a typo or an ordering mistake could open is refused.

        An unknown band name would never match, so the band it meant would pass.
        A band in both lists is ambiguous. And the gate must not weaken as risk
        rises: above a failing band every band fails, and above a reviewed band
        every band is reviewed or fails.
        """
        for name in self.review_bands + self.fail_bands:
            if name not in BAND_ORDER:
                raise ValueError(f"unknown band {name!r} in gate (expected one of {', '.join(BAND_ORDER)})")
        both = sorted(set(self.review_bands) & set(self.fail_bands), key=BAND_ORDER.index)
        if both:
            raise ValueError(f"band(s) {', '.join(both)} are in both review_bands and fail_bands")
        gated = set(self.review_bands) | set(self.fail_bands)
        for i, name in enumerate(BAND_ORDER):
            for above in BAND_ORDER[i + 1 :]:
                if name in self.fail_bands and above not in self.fail_bands:
                    raise ValueError(f"{name} fails but {above}, a higher band, does not")
                if name in gated and above not in gated:
                    raise ValueError(f"{name} is gated but {above}, a higher band, is not")
        return self


class Promise(BaseModel):
    breaking_access: list[ToolAccess] = Field(
        default_factory=lambda: [
            ToolAccess.WRITE,
            ToolAccess.DELETE,
            ToolAccess.EXECUTE,
            ToolAccess.EXTERNAL_SEND,
            ToolAccess.FINANCIAL,
        ]
    )
    breaking_data: list[DataClass] = Field(
        default_factory=lambda: [DataClass.PII, DataClass.HEALTH, DataClass.FINANCIAL, DataClass.CREDENTIAL]
    )
    # Declared autonomy at or below this means "a human approves actions".
    max_autonomy_with_human: int = Field(default=2, ge=0, le=5)


class PolicyCapability(BaseModel):
    suffix: str
    access: ToolAccess
    irreversible: bool = False


class PolicyCatalogEntry(BaseModel):
    system: str
    capabilities: list[PolicyCapability]
    data: list[DataClass] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    source: str = "organisation policy"


class Policy(BaseModel):
    apiVersion: str = API_VERSION
    name: str = "built-in defaults"
    weights: Weights = Field(default_factory=Weights)
    bands: Bands = Field(default_factory=Bands)
    gate: Gate = Field(default_factory=Gate)
    promise: Promise = Field(default_factory=Promise)
    # Added to the built-in read-only list (never replaces it).
    read_only_commands: list[str] = Field(default_factory=list)
    # Organisation MCP servers; matched before the built-in catalogue.
    catalog: list[PolicyCatalogEntry] = Field(default_factory=list)
    # Extra serialized tool-definition files to scan (repo-relative paths).
    tool_definition_files: list[str] = Field(default_factory=list)
    # Provenance, filled by load().
    path: str | None = None
    sha256: str | None = None

    @property
    def is_default(self) -> bool:
        return self.path is None

    def warnings(self) -> list[str]:
        """Valid but worth saying out loud every time the policy is used."""
        out = []
        if not self.gate.review_bands and not self.gate.fail_bands:
            out.append(
                "the gate lists no band: AA-001 never reviews or fails on its risk band "
                "(UNKNOWN capabilities and AA-002 still gate). Report-only use; "
                "add bands to review_bands or fail_bands to gate on risk"
            )
        return out


_DEFAULT = Policy()
_current: Policy = _DEFAULT


def current() -> Policy:
    return _current


def activate(policy: Policy) -> None:
    global _current
    _current = policy


def reset() -> None:
    activate(_DEFAULT)


def load(path: str) -> Policy:
    with open(path, "rb") as fh:
        raw_bytes = fh.read()
    try:
        raw = yaml.safe_load(raw_bytes) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path}: invalid policy YAML\n{exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: policy root must be a mapping")
    if raw.get("apiVersion", API_VERSION) != API_VERSION:
        raise ManifestError(f"{path}: unsupported policy apiVersion {raw.get('apiVersion')!r} (expected {API_VERSION!r})")
    raw.setdefault("apiVersion", API_VERSION)
    raw.pop("path", None)
    raw.pop("sha256", None)
    try:
        pol = Policy.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(f"{path}: invalid policy\n{exc}") from exc
    pol.path = path
    pol.sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return pol


def discover(directory: str) -> str | None:
    p = os.path.join(directory, DEFAULT_FILE)
    return p if os.path.isfile(p) else None


def describe() -> dict | None:
    """What the report records about the active policy (None for defaults)."""
    p = current()
    if p.is_default:
        return None
    return {"name": p.name, "path": p.path, "sha256": p.sha256}
