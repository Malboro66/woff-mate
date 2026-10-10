"""Synthetic sources and explicit complete-roster domain contracts for #96.

The runtime factory reconstructs the attested physical envelope, not a padded
legacy payload. Complete membership in domain tests is stipulated by the test;
it is never attributed to the simulator's partial detailed-record family.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from ..campaign_engine import CampaignEngine
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..ingestion.outcome import ProcessingReason
from ..parsers.dossier_parser import WoFFDossierParser
from .test_dossier_parser import _encode_dossier


def verified_dossier_lines(
    fields: Mapping[int, str], members: Sequence[str] = (),
) -> list[str]:
    """Place fictional field values in the observed pilot-detail envelope.

    Legacy synthetic member values are expressed as fictional pilot details:
    Lieutenant becomes Flight Lieutenant, missing extension fields stay Null.
    This is fixture construction, never production recognition or provenance.
    """
    if len(members) > 16:
        raise ValueError("The observed pilot block has sixteen physical slots")
    lines = ["Null"] * 161
    lines[0] = "160"
    lines[63:79] = ["N/A"] * 16
    lines[113:129] = ["N/A"] * 16
    for index, value in fields.items():
        if index not in range(63, 79) and index not in range(113, 129):
            lines[index] = value
    for index, member in enumerate(members, start=63):
        parts = member.split(";")
        if parts[0] == "Lieutenant":
            parts[0] = "Flight Lieutenant"
        if 26 <= len(parts) < 36:
            parts.extend(["Null"] * (36 - len(parts)))
        lines[index] = ";".join(parts)
    lines[81] = str(len(members))
    lines[112] = "Captain;Context;Only"
    lines[153] = ""
    return lines


def verified_fixture(lines: Sequence[str]) -> list[str]:
    """Re-express a legacy fixture's fictional values in verified physical slots."""
    fields = {index: value for index, value in enumerate(lines[:101])}
    fields[0] = "160"
    members = [value for value in lines[101:] if ";" in value]
    return verified_dossier_lines(fields, members)


class CompleteRosterDomainHarness(FileProcessor):
    """Exercise real engine transactions with stipulated complete test models.

    FileProcessor supplies the existing digest/exception/result envelope. This
    test-only adapter calls the engine's complete-roster interface explicitly;
    it does not exercise or bypass admission in any production instance.
    Runtime admission and partial integrity have separate real FileProcessor
    regressions. No persistence, reconciliation or exception handler is mocked.
    """
    def _process_text(self, path, fname, snapshot=None, *, dependent_identity=None, slot_epoch=None):
        if "dossier" not in fname:
            return super()._process_text(
                path, fname, snapshot,
                dependent_identity=dependent_identity, slot_epoch=slot_epoch,
            )
        data, name = self._parser_input(path, snapshot)
        parser = WoFFDossierParser()
        if not parser.parse_bytes(data, name) or parser.pilot is None:
            return ProcessingReason.PARSER_REJECTED
        pilot_id = self.campaign_engine.process_dossier_import(
            pilot=parser.pilot, decorations=parser.decorations,
            wingmen=parser.wingmen, identity=self._dossier_identity(snapshot, slot_epoch),
            roster_complete=True,
        )
        return None if pilot_id else ProcessingReason.PERSISTENCE_REJECTED


@pytest.fixture
def complete_roster_domain(tmp_path):
    db = DatabaseManager(str(tmp_path / "complete-domain.sqlite"))
    harness = CompleteRosterDomainHarness(
        db, CampaignEngine(db), stability_timeout=0.1, stability_interval=0.001,
    )
    yield db, harness, tmp_path / "Pilot1Dossier.txt"
    db.close()
