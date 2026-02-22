"""Tests for CrossAgentCorrelator."""

from phoenix_guardian.agents.cross_agent_correlator import CrossAgentCorrelator


def test_pain_plus_shadow_correlation():
    correlator = CrossAgentCorrelator()
    sv = {"alert_level": "critical", "distress_minutes": 61}
    ts = {"active_shadows": [{"drug_name": "Morphine", "alert_fired": True}]}
    result = correlator.correlate("test-patient", sv_result=sv, ts_result=ts)
    assert len(result) > 0
    assert result[0]["correlation_id"] == "pain_plus_analgesic_tolerance"


def test_no_correlation_when_clear():
    correlator = CrossAgentCorrelator()
    sv = {"alert_level": "clear"}
    ts = {"active_shadows": []}
    result = correlator.correlate("test-patient", sv_result=sv, ts_result=ts)
    assert len(result) == 0


def test_rare_disease_plus_shadow():
    correlator = CrossAgentCorrelator()
    zh = {"status": "zebra_found"}
    ts = {"active_shadows": [{"drug_name": "Metformin", "alert_fired": True}]}
    result = correlator.correlate("test-patient", zh_result=zh, ts_result=ts)
    assert len(result) > 0
    assert result[0]["correlation_id"] == "rare_disease_plus_shadow"


def test_ghost_plus_distress():
    correlator = CrossAgentCorrelator()
    zh = {"ghost_protocol_activated": True}
    sv = {"alert_level": "critical"}
    result = correlator.correlate("test-patient", zh_result=zh, sv_result=sv)
    assert len(result) > 0
    assert result[0]["correlation_id"] == "ghost_plus_distress"


def test_multiple_correlations():
    """Tests that multiple rules can fire simultaneously."""
    correlator = CrossAgentCorrelator()
    sv = {"alert_level": "critical"}
    ts = {"active_shadows": [{"drug_name": "Morphine", "alert_fired": True}]}
    zh = {"status": "zebra_found", "ghost_protocol_activated": True}
    result = correlator.correlate("test-patient", sv_result=sv, ts_result=ts, zh_result=zh)
    ids = [r["correlation_id"] for r in result]
    assert "pain_plus_analgesic_tolerance" in ids
    assert "rare_disease_plus_shadow" in ids
    assert "ghost_plus_distress" in ids
