from minagent.core.stats import RunStats


def test_stats_update_from_usage():
    stats = RunStats()
    stats.update_from_usage({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    stats.update_from_usage({"prompt_tokens": 3, "total_tokens": 3})

    assert stats.llm_call_count == 0  # not auto incremented
    assert stats.total_prompt_tokens == 13
    assert stats.total_completion_tokens == 5
    assert stats.total_tokens == 18


def test_stats_add_error():
    stats = RunStats()
    stats.add_error("timeout")
    assert stats.errors == ["timeout"]


def test_stats_to_dict():
    stats = RunStats(turn_count=2, llm_call_count=2, tool_call_count=3)
    stats.update_from_usage({"total_tokens": 100})
    d = stats.to_dict()
    assert d["turn_count"] == 2
    assert d["tool_call_count"] == 3
    assert d["total_tokens"] == 100
    assert "errors" in d
