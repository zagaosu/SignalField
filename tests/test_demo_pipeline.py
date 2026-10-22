from __future__ import annotations

from app.pipeline.evidence import quote_verified


def test_demo_pipeline_produces_verifiable_events(run_demo):
    state = run_demo()
    assert state["status"] == "completed"
    assert state["stop_reason"] == "coverage_sufficient"
    assert len(state["events"]) == 4
    assert state["usage"]["remote_calls"] == 0
    assert state["usage"]["simulated"] is True
    assert state["usage"]["search_calls"] <= 8
    assert state["usage"]["read_attempts"] <= 15
    assert state["usage"]["model_calls"] <= 9
    assert state["actions"] and state["actions"][0]["resolved_gaps"] >= 1
    assert {gap["status"] for gap in state["gaps"]} == {"resolved"}

    assert all(event["facts"] for event in state["events"])
    for event in state["events"]:
        source_ids = {source["document_id"] for source in event["sources"]}
        for fact in event["facts"]:
            assert fact["status"] == "supported"
            assert fact["evidence"]
            for evidence in fact["evidence"]:
                assert evidence["verified"] is True
                assert evidence["document_id"] in source_ids
                doc = next(d for d in state["documents"] if d["id"] == evidence["document_id"])
                assert quote_verified(evidence["quote"], doc["content"])
    assert state["verification"]["citation_support_rate"] == 100.0
    assert state["verification"]["evidence_verified"] == state["verification"]["evidence_total"]
    stages = [item["to"] for item in state["stage_history"]]
    assert stages[:6] == [
        "created",
        "planning",
        "searching",
        "reading",
        "extracting",
        "checking_gaps",
    ]
    assert stages[-2:] == ["verifying", "done"]
    assert not any("非预期状态转移" in warning for warning in state["warnings"])
    demo_domains = {
        source["domain"] for event in state["events"] for source in event["sources"]
    }
    assert demo_domains
    assert all(domain.endswith(".invalid") for domain in demo_domains)
    longtrace = next(event for event in state["events"] if event["event_key"] == "longtrace-1-0")
    assert longtrace["event_date"]
    assert not any("发布日期不明确" in item for item in longtrace["unresolved"])


def test_repost_is_merged_and_marked_duplicate(run_demo):
    state = run_demo()
    duplicates = [doc for doc in state["documents"] if doc.get("duplicate_of")]
    assert duplicates
    aster_events = [event for event in state["events"] if event["event_key"] == "aster-agent-kit-0-8"]
    assert len(aster_events) == 1
    assert len(aster_events[0]["sources"]) == 1
    assert "agentweekly.invalid" not in {
        source["domain"] for source in aster_events[0]["sources"]
    }


def test_single_topic_demo_respects_selection(run_demo):
    state = run_demo(topics=["推理部署"])
    assert state["status"] == "completed"
    assert state["events"]
    assert all(event["topic"] == "推理部署" for event in state["events"])
    assert len(state["events"]) == 1


def test_demo_custom_topic_returns_no_fabricated_events(run_demo):
    state = run_demo(topics=["量子网络调度"])
    assert state["status"] == "completed"
    assert state["stop_reason"] == "no_results"
    assert state["events"] == []
    assert state["usage"]["remote_calls"] == 0
