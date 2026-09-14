"""Closed playable identities derived from one recoverable source value.

The legacy ``pilots.nation`` column stores evidence, never a playable identity.
Canonical values are read-only projections, so no data migration or second
writable authority is needed. Display labels must not be used for rules.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from .maps import NATION_MAP


class NationCode(str, Enum):
    GB = "GB"
    FR = "FR"
    DE = "DE"
    US = "US"
    BE = "BE"


class ServiceCode(str, Enum):
    RFC = "RFC"
    RNAS = "RNAS"
    RAF = "RAF"


NationState = Literal["known", "missing", "unsupported"]
ServiceState = Literal["known", "missing_or_unknown"]


def normalize_nation_evidence(raw: Optional[str]) -> str:
    """Normalize whitespace only; domain recognition is a separate operation."""
    return raw.strip() if raw else ""


@dataclass(frozen=True)
class NationService:
    """Immutable interpretation of source evidence, including legacy values."""

    nation_raw: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "nation_raw", normalize_nation_evidence(self.nation_raw))

    @property
    def nation_code(self) -> Optional[NationCode]:
        alias = NATION_MAP.get(self.nation_raw.casefold())
        return NationCode(alias[0]) if alias else None

    @property
    def service_code(self) -> Optional[ServiceCode]:
        alias = NATION_MAP.get(self.nation_raw.casefold())
        return ServiceCode(alias[1]) if alias and alias[1] else None

    @property
    def nation_state(self) -> NationState:
        if self.nation_code is not None:
            return "known"
        return "unsupported" if self.nation_raw else "missing"

    @property
    def service_state(self) -> ServiceState:
        return "known" if self.service_code is not None else "missing_or_unknown"

    def presentation(self) -> "NationServicePresentation":
        """Copy only canonical identities and safe labels to presentation."""
        labels = {
            NationCode.GB: "Britain", NationCode.FR: "France",
            NationCode.DE: "Germany", NationCode.US: "USA", NationCode.BE: "Belgium",
        }
        nation_label = labels.get(self.nation_code) if self.nation_code else None
        if self.nation_state == "unsupported":
            nation_label = "Unsupported nation"
        return NationServicePresentation(
            self.nation_code, self.service_code, self.nation_state,
            self.service_state, nation_label,
            self.service_code.value if self.service_code else None,
        )


@dataclass(frozen=True)
class NationServicePresentation:
    """Small #136 value contract for #81; no source paths or live UI binding."""

    nation_code: Optional[NationCode]
    service_code: Optional[ServiceCode]
    nation_state: NationState
    service_state: ServiceState
    nation_label: Optional[str]
    service_label: Optional[str]
