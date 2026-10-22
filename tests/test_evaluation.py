from __future__ import annotations

import csv

from evaluation.harness import ANNOTATION_COLUMNS, run_all


def test_replay_evaluation_is_runnable_and_separates_profiles(tmp_path):
    result = run_all(tmp_path, ["A", "B", "C"])
    payload = result["payload"]
    assert payload["mode"] == "replay"
    assert payload["synthetic"] is True
    assert payload["remote_calls"] == 0
    assert len(payload["results"]) == 24
    aggregates = {item["profile"]: item for item in payload["aggregates"]}
    assert set(aggregates) == {"A", "B", "C"}
    assert aggregates["C"]["reference_event_coverage"] >= aggregates["B"]["reference_event_coverage"]
    assert aggregates["C"]["reference_fact_coverage"] >= aggregates["B"]["reference_fact_coverage"]
    assert all(agg["citation_support_rate"] == 1.0 for agg in aggregates.values())
    assert all(agg["duplicate_rate"] == 0.0 for agg in aggregates.values())
    assert result["json_path"].exists()
    assert result["annotation_path"].exists()
    with result["annotation_path"].open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert set(rows[0].keys()) == set(ANNOTATION_COLUMNS)
    assert any(row["event_id"] == "__NO_EVENT__" for row in rows)
    assert any("__NO_EVENT__" in row["event_id"] for row in rows)
