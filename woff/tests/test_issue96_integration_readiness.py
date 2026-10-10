"""Synthetic production-path evidence across physical SQLite reopen boundaries."""

from __future__ import annotations

from .dossier_support import CompleteRosterDomainHarness

import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from unittest.mock import patch

import pytest

from ..campaign_engine import CampaignEngine
from ..campaign_namespace import campaign_namespace_for_root
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..ingestion.outcome import ProcessingReason
from ..models import WoFFWingman
from ..parsers.dossier_parser import WoFFDossierParser
from .test_dossier_parser import _encode_dossier
from .test_dossier_transactions import _dossier_bytes, _wingman
from .test_issue96_codex_exception_regressions import _observed
from .test_issue96_observed_partial_roster import _physical_lines
from .test_wingman_identity_migration import _LEGACY_SQUAD_MEMBERS_DDL

import woff_query


def _homonyms(*, partial=True, second=True, day=10, wounded=False):
    lines = _physical_lines(second_pilot=second, day=day)
    lines[3:6] = ["Lieutenant", "James", "Hartley"]
    lines[60] = "Active"
    lines[83] = "No. 56 Squadron"
    for index in (63, 65):
        if index == 65 and not second:
            continue
        fields = lines[index].split(";")
        fields[:3] = ["Flight Lieutenant", "John", "Smith"]
        if index == 65:
            fields[16:19] = ["6", "7", "1895"]
            fields[24] = "2/4/1916"
            if wounded:
                fields[5] = "Wounded"
        lines[index] = ";".join(fields)
    if partial:
        return _encode_dossier(lines, "Pilot1Dossier.txt")
    members = [lines[63]] + ([lines[65]] if second else []) + [lines[113]]
    # Distinct dates make complete observations independently replayable.
    complete = ["Null"] * 104
    for index in (1, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 16, 17,
                  41, 46, 52, 60, 83, 84, 88, 89):
        complete[index] = lines[index]
    return _encode_dossier(complete + members, "Pilot1Dossier.txt")


def _open(path):
    db = DatabaseManager(str(path))
    return db, FileProcessor(
        db, CampaignEngine(db), stability_timeout=0.1, stability_interval=0.001
    )


def _apply(processor, source, data):
    source.write_bytes(data)
    return processor.process(str(source), "modified")


def _apply_complete(processor, source, data):
    """Explicit historical complete-census engine contract, not source admission."""
    source.write_bytes(data)
    harness = CompleteRosterDomainHarness(processor.db_manager, processor.campaign_engine, stability_timeout=0.1, stability_interval=0.001)
    return harness.process(str(source), "modified")


def _state(db, source):
    with db.transaction():
        state = db.load_dossier_state(
            "James Hartley", campaign_namespace_for_root(str(source.parent)), 1
        )
    assert state is not None
    return state


def _close(db):
    connection = db._get_conn()
    db.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def _dump(db):
    # Reopening may reorder meta rowids; compare every exact SQL statement.
    return sorted(db._get_conn().iterdump())


def _healthy(db):
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
    assert db._get_conn().execute("PRAGMA integrity_check").fetchone() == ("ok",)


def _legacy(path, source, variant):
    """Create the actual 3.4 table contract with historical IDs and digest."""
    db, processor = _open(path)
    raw = _homonyms()
    assert _apply(processor, source, raw).acknowledged_generation
    pilot_id = _state(db, source).pilot_id
    _close(db)
    historical = {"history-john", "history-casey", "history-other"}
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE squad_members")
        connection.execute(_LEGACY_SQUAD_MEMBERS_DDL)
        names = [("history-john", "John", "Smith"),
                 ("history-casey", "Casey", "Clark"),
                 ("history-other", "Old", "Other")]
        connection.executemany(
            "INSERT INTO squad_members (id,pilotId,fName,sName,status,bio) "
            "VALUES (?,?,?,?,?,?)",
            [(member_id, pilot_id, first, last, "In Service", "Historical bio")
             for member_id, first, last in names],
        )
        connection.execute(
            "INSERT INTO wingmen_personalities "
            "(wingmanId,pilotId,personality_trait) VALUES (?,?,?)",
            ("history-john", pilot_id, "Historical steady"),
        )
        connection.execute(
            "INSERT INTO wingmen_memory "
            "(id,wingmanId,event_type,event_date,description) VALUES (?,?,?,?,?)",
            ("history-memory", "history-john", "mission", "1915-11-09", "History"),
        )
        roster = [[first, last, "In Service"] for _, first, last in names]
        if variant == "list":
            payload = roster
        else:
            payload = {"version": 1, "squadron": "No. 56 Squadron",
                       "baseline_pending": False, "wingmen": roster, "candidate": None}
            if variant == "v2-no-provenance":
                payload["version"] = 2
                payload["wingmen"] = [[member_id, first, last, "In Service"]
                                      for member_id, first, last in names]
        if variant == "absent":
            connection.execute("DELETE FROM meta WHERE key=?", ("dossier_roster:" + pilot_id,))
        else:
            connection.execute("UPDATE meta SET value=? WHERE key=?",
                               (json.dumps(payload), "dossier_roster:" + pilot_id))
        connection.execute("DELETE FROM meta WHERE key=?", ("dossier_partial_digest:" + pilot_id,))
        connection.execute("UPDATE meta SET value='3.4' WHERE key='schema_version'")
    return raw, pilot_id, historical


def _ownership(db):
    connection = db._get_conn()
    return (connection.execute("SELECT * FROM wingmen_personalities ORDER BY wingmanId").fetchall(),
            connection.execute("SELECT * FROM wingmen_memory ORDER BY id").fetchall())


@pytest.mark.parametrize("variant", ["v1", "list", "absent", "v2-no-provenance"])
def test_legacy_upgrade_queries_and_identity_survive_real_reopens(tmp_path, variant):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, historical = _legacy(path, source, variant)
    db, processor = _open(path)
    try:
        assert {row["id"] for row in db.get_wingmen_with_identity_by_pilot(pilot_id)} == historical
        ownership = _ownership(db)
        backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
        assert len(backups) == 1
        with closing(sqlite3.connect(backups[0])) as backup:
            assert {row[0] for row in backup.execute("SELECT id FROM squad_members")} == historical
            assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert backup.execute("PRAGMA foreign_key_check").fetchall() == []
        assert _apply(processor, source, raw).acknowledged_generation
        state = _state(db, source)
        assert state.pilot_id == pilot_id
        assert state.roster_format_version == 2 and state.roster_baseline_pending
        assert state.roster_candidate is None
        assert state.retired_wingman_ids == historical
        observed_ids = {member.wingman_id for member in state.wingmen}
        assert len(observed_ids) == 3 and observed_ids.isdisjoint(historical)
        assert db._get_conn().execute("SELECT COUNT(*) FROM squad_members").fetchone() == (6,)
        public = db.get_wingmen_by_pilot(pilot_id)
        rich = db.get_wingmen_with_identity_by_pilot(pilot_id)
        assert len(public) == 3  # RED before the retired-query correction.
        assert {row["id"] for row in rich} == observed_ids
        assert {row["id"] for row in db._wingmen.get_wingmen_with_identity_by_pilot(
            pilot_id, include_retired=True
        )} == historical | observed_ids
        assert all(set(row) == {"fName", "sName", "status"} for row in public)
        assert sum(row["fName"] == "John" and row["sName"] == "Smith" for row in public) == 2
        assert db._wingmen.get_wingmen_by_pilot(pilot_id) == public
        assert _ownership(db) == ownership
        historical_rows = db._get_conn().execute(
            "SELECT id,fName,sName,status,bio,birthDate,evidenceDate,evidenceLocation "
            "FROM squad_members WHERE id LIKE 'history-%' ORDER BY id"
        ).fetchall()
        after_upgrade = _dump(db)
        _close(db)
        db, processor = _open(path)
        assert _dump(db) == after_upgrade
        assert _apply(processor, source, raw).acknowledged_generation
        assert _dump(db) == after_upgrade
        changed = _homonyms(day=11, second=False)
        assert _apply(processor, source, changed).acknowledged_generation
        changed_state = _state(db, source)
        assert changed_state.roster_baseline_pending and changed_state.roster_candidate is None
        assert changed_state.retired_wingman_ids == historical
        assert {member.wingman_id for member in changed_state.wingmen} == observed_ids
        assert changed_state.dossier_digest == sha256(changed).hexdigest()
        with db.transaction():
            assert db.partial_dossier_digest_recorded(pilot_id, sha256(changed).hexdigest())
        binding = db.get_slot_binding(campaign_namespace_for_root(str(tmp_path)), 1)
        assert binding is not None and binding.pilot_id == pilot_id
        assert binding.dossier_digest == sha256(changed).hexdigest()
        second_snapshot = _dump(db)
        _close(db)
        db, processor = _open(path)
        assert _dump(db) == second_snapshot
        assert _apply(processor, source, changed).acknowledged_generation
        assert _dump(db) == second_snapshot
        assert _ownership(db) == ownership
        assert db._get_conn().execute(
            "SELECT id,fName,sName,status,bio,birthDate,evidenceDate,evidenceLocation "
            "FROM squad_members WHERE id LIKE 'history-%' ORDER BY id"
        ).fetchall() == historical_rows
        assert len(db.get_wingmen_by_pilot(pilot_id)) == 3
        assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (0,)
        assert list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite")) == backups
        _healthy(db)
    finally:
        db.close()


@pytest.mark.parametrize("invalid", ["unknown", "duplicate", "foreign", "resolved",
                                     "active-overlap", "candidate-overlap"])
def test_invalid_retirement_scope_rejects_queries_without_guessing(tmp_path, invalid, capsys):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, _ = _legacy(path, source, "v1")
    db, processor = _open(path)
    try:
        assert _apply(processor, source, raw).acknowledged_generation
        with db.transaction() as connection:
            key = "dossier_roster:" + pilot_id
            payload = json.loads(connection.execute(
                "SELECT value FROM meta WHERE key=?", (key,)
            ).fetchone()[0])
            if invalid == "unknown":
                payload["retired_wingman_ids"].append("unknown-history")
            elif invalid == "duplicate":
                payload["retired_wingman_ids"].append("history-john")
            elif invalid == "foreign":
                connection.execute("INSERT INTO pilots (id,name) VALUES ('other-pilot','Other Pilot')")
                connection.execute("INSERT INTO squad_members (id,pilotId) VALUES ('foreign-history','other-pilot')")
                payload["retired_wingman_ids"].append("foreign-history")
            elif invalid == "resolved":
                payload["retired_wingman_ids"].append(payload["wingmen"][0][0])
            else:
                member = ["history-john", "John", "Smith", "In Service"]
                if invalid == "active-overlap":
                    payload["wingmen"].append(member)
                else:
                    payload["candidate"] = {"squadron": "No. 56 Squadron", "wingmen": [member]}
            connection.execute("UPDATE meta SET value=? WHERE key=?", (json.dumps(payload), key))
        before = _dump(db)
        for query in (db.get_wingmen_by_pilot, db.get_wingmen_with_identity_by_pilot,
                      db._wingmen.get_wingmen_by_pilot):
            with pytest.raises(sqlite3.DatabaseError):
                query(pilot_id)
        assert woff_query.main(["--db", str(path), "--pilot-id", pilot_id,
                                "--wingmen", "--format", "json"]) != 0
        assert capsys.readouterr().out == ""
        assert _apply(processor, source, raw).acknowledged_generation is None
        assert _dump(db) == before
        _healthy(db)
    finally:
        db.close()


def test_retired_history_cannot_emit_compatibility_missing_events(tmp_path):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, _ = _legacy(path, source, "v1")
    db, processor = _open(path)
    try:
        assert _apply(processor, source, raw).acknowledged_generation
        state = _state(db, source)
        current = []
        for member in state.wingmen:
            assert member.wingman_id is not None
            current.append(WoFFWingman(id=member.wingman_id, pilotId=pilot_id,
                                      fName=member.first_name, sName=member.last_name,
                                      status=member.status))
        with patch("woff.campaign_engine.narrative_generator.generate_wingman_event",
                   return_value="Synthetic missing event") as event:
            assert CampaignEngine(db).process_wingmen_changes(pilot_id, current, "1915-11-10")
            event.assert_not_called()  # RED: three historical IDs were "missing".
        assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (0,)
    finally:
        db.close()


def test_compatibility_cannot_reintroduce_an_explicitly_retired_id(tmp_path):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, _ = _legacy(path, source, "v1")
    db, processor = _open(path)
    try:
        assert _apply(processor, source, raw).acknowledged_generation
        state = _state(db, source)
        current = []
        for member in state.wingmen:
            assert member.wingman_id is not None
            current.append(WoFFWingman(id=member.wingman_id, pilotId=pilot_id,
                                      fName=member.first_name, sName=member.last_name,
                                      status=member.status))
        current.append(WoFFWingman(id="history-john", pilotId=pilot_id,
                                  fName="John", sName="Smith", status="In Service"))
        before = _dump(db)
        with patch("woff.campaign_engine.narrative_generator.generate_wingman_event",
                   return_value="Synthetic arrival") as event:
            assert CampaignEngine(db).process_wingmen_changes(
                pilot_id, current, "1915-11-10"
            ) is False
            event.assert_not_called()
        assert _dump(db) == before
    finally:
        db.close()


def test_changed_partial_cannot_retire_a_trusted_legacy_complete_baseline(tmp_path):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    _, pilot_id, historical = _legacy(path, source, "v1")
    complete = _dossier_bytes(wingmen=(
        _wingman("John", "Smith"), _wingman("Casey", "Clark"),
        _wingman("Old", "Other"),
    ))
    db, processor = _open(path)
    try:
        # A genuinely complete legacy generation, not the same observed hash.
        # v1 alone cannot prove that the old complete baseline was partial.
        with db.transaction() as connection:
            connection.execute(
                "UPDATE pilot_slot_bindings SET dossier_digest=? WHERE pilotId=?",
                (sha256(complete).hexdigest(), pilot_id),
            )
        before = _dump(db)
        outcome = _apply(processor, source, _homonyms(day=11))
        assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
        assert outcome.acknowledged_generation is None
        assert _dump(db) == before
        assert not _state(db, source).roster_baseline_pending
        assert _state(db, source).retired_wingman_ids == frozenset()
        assert {row["id"] for row in db.get_wingmen_with_identity_by_pilot(pilot_id)} == historical
        _close(db)
        db, processor = _open(path)
        assert _dump(db) == before
        assert _apply(processor, source, _homonyms(day=11)).acknowledged_generation is None
        assert _dump(db) == before
    finally:
        db.close()


@pytest.mark.parametrize("uppercase_meta", [False, True])
def test_readonly_cli_roster_excludes_retired_history_and_keeps_export_shape(tmp_path, capsys, uppercase_meta):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, _ = _legacy(path, source, "v1")
    db, processor = _open(path)
    try:
        assert _apply(processor, source, raw).acknowledged_generation
        if uppercase_meta:
            # SQLite identifiers are case-insensitive, including legacy names.
            with db.transaction() as connection:
                connection.execute("ALTER TABLE meta RENAME TO meta_case_fixture")
                connection.execute("ALTER TABLE meta_case_fixture RENAME TO META")
            _close(db)
            db, processor = _open(path)
        assert len(db.get_wingmen_by_pilot(pilot_id)) == 3
        before = _dump(db)
        assert woff_query.main(["--db", str(path), "--pilot-id", pilot_id,
                                "--wingmen", "--format", "json"]) == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 3
        assert all(set(row) == {"pilot_id", "rank", "fName", "sName", "status",
                               "skill", "bio"} for row in rows)
        assert sum(row["fName"] == "John" for row in rows) == 2
        assert _dump(db) == before
    finally:
        db.close()


def test_readonly_cli_keeps_legacy_schema_without_retirement_metadata(tmp_path, capsys):
    path = tmp_path / "legacy-reader.sqlite"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE pilots (id TEXT PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO pilots VALUES ('legacy','Synthetic Pilot')")
        connection.execute(_LEGACY_SQUAD_MEMBERS_DDL)
        connection.execute(
            "INSERT INTO squad_members (id,pilotId,fName,sName,status) "
            "VALUES ('history','legacy','John','Smith','In Service')"
        )
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        woff_query.show_wingmen(connection, "legacy", woff_query.Colors(False),
                               woff_query.argparse.Namespace(format="json"))
        assert connection.total_changes == 0 and not connection.in_transaction
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='meta'").fetchall() == []
    rows = json.loads(capsys.readouterr().out)
    assert rows == [{"pilot_id": "legacy", "rank": None, "fName": "John",
                     "sName": "Smith", "status": "In Service", "skill": None, "bio": None}]


@pytest.mark.parametrize("boundary", ["load_resolved_dossier_roster", "save_dossier_roster_state",
                                      "record_partial_dossier_digest"])
def test_legacy_upgrade_failure_rolls_back_across_reopen(tmp_path, boundary):
    path, source = tmp_path / "legacy.sqlite", tmp_path / "Pilot1Dossier.txt"
    raw, pilot_id, historical = _legacy(path, source, "v1")
    db, processor = _open(path)
    try:
        before = _dump(db)
        original = getattr(db, boundary)

        def fail_after_write(*args, **kwargs):
            original(*args, **kwargs)
            raise sqlite3.IntegrityError("Synthetic boundary failure")

        with patch.object(db, boundary, side_effect=fail_after_write):
            assert _apply(processor, source, raw).acknowledged_generation is None
        assert _dump(db) == before
        _close(db)
        db, processor = _open(path)
        assert _dump(db) == before
        assert {row["id"] for row in db.get_wingmen_with_identity_by_pilot(pilot_id)} == historical
        assert _apply(processor, source, raw).acknowledged_generation
        recovered = _dump(db)
        _close(db)
        db, processor = _open(path)
        assert _apply(processor, source, raw).acknowledged_generation
        assert _dump(db) == recovered
        _healthy(db)
    finally:
        db.close()


@pytest.mark.parametrize("candidate", [False, True])
def test_trusted_homonym_baseline_and_candidate_survive_partial_reopens(tmp_path, candidate):
    path, source = tmp_path / "trusted.sqlite", tmp_path / "Pilot1Dossier.txt"
    db, processor = _open(path)
    try:
        assert _apply_complete(processor, source, _homonyms(partial=False)).acknowledged_generation
        initial = _state(db, source)
        ids = {member.wingman_id for member in initial.wingmen}
        for member_id in ids:
            assert member_id is not None
            assert db.save_wingman_personality(member_id, initial.pilot_id,
                                              {"personality_trait": "Steady " + member_id})
            assert db.save_wingman_memory(member_id, "mission", "1915-11-10", "Synthetic " + member_id)
        ownership = _ownership(db)
        if candidate:
            assert _apply_complete(processor, source, _homonyms(partial=False, second=False, day=11)).acknowledged_generation
        trusted = _state(db, source)
        assert (trusted.roster_candidate is not None) == candidate
        metadata = db._get_conn().execute("SELECT value FROM meta WHERE key=?",
                                         ("dossier_roster:" + initial.pilot_id,)).fetchone()
        raw = _homonyms(second=False, day=12)
        assert _apply(processor, source, raw).acknowledged_generation
        assert _state(db, source).wingmen == trusted.wingmen
        assert _state(db, source).roster_candidate == trusted.roster_candidate
        assert db._get_conn().execute("SELECT value FROM meta WHERE key=?",
                                     ("dossier_roster:" + initial.pilot_id,)).fetchone() == metadata
        snapshot = _dump(db)
        _close(db)
        db, processor = _open(path)
        assert _apply(processor, source, raw).acknowledged_generation
        assert _dump(db) == snapshot
        assert not _state(db, source).roster_baseline_pending
        if not candidate:
            assert _apply_complete(processor, source, _homonyms(partial=False, second=False, day=13)).acknowledged_generation
            assert _state(db, source).roster_candidate is not None
        assert _apply_complete(processor, source, _homonyms(partial=False, day=14)).acknowledged_generation
        assert _state(db, source).roster_candidate is None
        assert {row["id"] for row in db.get_wingmen_with_identity_by_pilot(initial.pilot_id)} == ids
        assert _ownership(db) == ownership
        assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (0,)
        wounded = _homonyms(partial=False, day=15, wounded=True)
        assert _apply_complete(processor, source, wounded).acknowledged_generation
        assert db._get_conn().execute("SELECT evidenceLocation,status FROM squad_members WHERE fName='John' ORDER BY evidenceLocation").fetchall() == [
            ("Synthetic town of Alex", "In Service"), ("Synthetic town of Blair", "Wounded")]
        assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (1,)
        last = _dump(db)
        _close(db)
        db, processor = _open(path)
        assert _apply_complete(processor, source, wounded).acknowledged_generation
        assert _dump(db) == last and _ownership(db) == ownership
        _healthy(db)
    finally:
        db.close()


@pytest.mark.parametrize("arity", [5, 6, 7])
def test_observed_structural_diagnostics_do_not_shift_or_transfer(tmp_path, arity):
    path, source = tmp_path / "physical.sqlite", tmp_path / "Pilot1Dossier.txt"
    db, processor = _open(path)
    try:
        assert _apply_complete(processor, source, _dossier_bytes()).acknowledged_generation
        trusted = _state(db, source)
        lines = _physical_lines()
        lines[3:6] = ["Lieutenant", "James", "Hartley"]
        lines[60], lines[83] = "Active", "No. 56 Squadron"
        lines[64] = ""  # Historical diagnostic: blank at physical line 65.
        lines[130] = ";".join(["Unrelated", "prose", "with", "exactly", "synthetic", "fields", "extra"][:arity])
        parser = WoFFDossierParser()
        raw = _encode_dossier(lines, source.name)
        assert parser.parse_bytes(raw, source.name)
        assert len(parser.raw_strings) == 161 and parser.raw_strings[64] == ""
        assert parser.roster_complete is False
        assert parser.pilot is not None and parser.pilot.squadron == "No. 56 Squadron"
        assert parser.pilot.aircraft == "Synthetic_Nieuport"
        assert len(parser.wingmen) == 3
        assert all(member.sName != "Only" for member in parser.wingmen)
        assert _apply(processor, source, raw).acknowledged_generation
        after = _state(db, source)
        assert after.roster_squadron == trusted.roster_squadron
        assert after.wingmen == trusted.wingmen
        assert not after.roster_baseline_pending and after.roster_candidate is None
        assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (0,)
        snapshot = _dump(db)
        assert _apply(processor, source, raw).acknowledged_generation
        assert _dump(db) == snapshot
    finally:
        db.close()


@pytest.mark.parametrize("position", [63, 113])
@pytest.mark.parametrize("status", ["", "   "])
def test_observed_empty_required_status_is_state_neutral(tmp_path, position, status):
    path, source = tmp_path / "status.sqlite", tmp_path / "Pilot1Dossier.txt"
    db, processor = _open(path)
    try:
        assert _apply(processor, source, _observed()).acknowledged_generation
        before = _dump(db)
        for day in (11, 12):
            lines = _physical_lines(day=day)
            fields = lines[position].split(";")
            fields[5] = status
            lines[position] = ";".join(fields)
            outcome = _apply(processor, source, _encode_dossier(lines, source.name))
            assert outcome.reason is ProcessingReason.PARSER_REJECTED
            assert outcome.acknowledged_generation is None
            assert _dump(db) == before
    finally:
        db.close()
