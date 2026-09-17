from scripts.run_step211_langfuse_performance import latency_summary, overhead, percentile, tail_gate


def _workload(p95, p99):
    return {"wallLatencyMs": {"p95": p95, "p99": p99}}


def test_percentile_uses_nearest_rank_for_tail_samples():
    values = list(range(1, 101))
    assert percentile(values, 0.50) == 50
    assert percentile(values, 0.95) == 95
    assert percentile(values, 0.99) == 99
    assert latency_summary(values)["max"] == 100


def test_overhead_reports_absolute_and_percent_delta():
    assert overhead(125, 100) == {"deltaMs": 25, "deltaPercent": 25.0}
    assert overhead(8, 10) == {"deltaMs": -2, "deltaPercent": -20.0}


def test_tail_gate_uses_absolute_floor_for_fast_light_path():
    result = tail_gate("light", _workload(10, 15), _workload(28, 42))
    assert result["status"] == "PASS"
    assert result["allowedP95DeltaMs"] == 20
    assert result["allowedP99DeltaMs"] == 30


def test_tail_gate_rejects_material_strict_regression():
    result = tail_gate("strict_uncached", _workload(400, 500), _workload(550, 700))
    assert result["status"] == "FAIL"
