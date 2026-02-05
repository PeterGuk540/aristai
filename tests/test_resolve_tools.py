from mcp_server.tools import resolve


def test_rank_candidates_fuzzy_ordering():
    items = [(1, "CS408 Advanced Systems"), (2, "Intro to Biology")]
    ranked = resolve.rank_candidates(items, "CS408")
    assert ranked[0].id == 1
    assert ranked[0].confidence >= ranked[1].confidence


def test_rank_candidates_empty():
    ranked = resolve.rank_candidates([], "anything")
    assert ranked == []
