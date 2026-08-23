import unittest

from ..parsers.mission_log_parser import WoFFMissionLogParser


def _mission_log(date: str, time: str | None = None) -> bytes:
    time_attribute = f' Time="{time}"' if time is not None else ""
    return (
        "<Mission>"
        f'<Params Date="{date}"{time_attribute} Weather="Clear" />'
        "<Overview>Test briefing</Overview>"
        "</Mission>"
    ).encode("utf-8")


class TestMissionLogTemporalContract(unittest.TestCase):
    def test_valid_date_and_unpadded_time_are_canonical(self):
        parser = WoFFMissionLogParser()

        self.assertTrue(
            parser.parse_bytes(
                _mission_log("9/20/1915", "9:30"), "Mission.log"
            )
        )
        self.assertIsNotNone(parser.mission)
        assert parser.mission is not None
        self.assertEqual(
            (parser.mission.date, parser.mission.time),
            ("1915-09-20", "09:30"),
        )

    def test_missing_time_is_preserved_as_explicit_absence(self):
        parser = WoFFMissionLogParser()

        self.assertTrue(
            parser.parse_bytes(_mission_log("11/11/1918"), "Mission.log")
        )
        self.assertIsNotNone(parser.mission)
        assert parser.mission is not None
        self.assertEqual(
            (parser.mission.date, parser.mission.time),
            ("1918-11-11", ""),
        )

    def test_impossible_or_unrecognized_dates_are_rejected(self):
        for raw_date in ("2/30/1917", "Tomorrow"):
            with self.subTest(raw_date=raw_date):
                parser = WoFFMissionLogParser()
                self.assertFalse(
                    parser.parse_bytes(_mission_log(raw_date, "10:30"), "Mission.log")
                )
                self.assertIsNone(parser.mission)

    def test_present_but_invalid_time_is_rejected(self):
        parser = WoFFMissionLogParser()

        self.assertFalse(
            parser.parse_bytes(
                _mission_log("11/11/1918", "24:00"), "Mission.log"
            )
        )
        self.assertIsNone(parser.mission)


if __name__ == "__main__":
    unittest.main()
