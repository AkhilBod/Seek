from backend.app.vector_store import keyword_tsquery, reciprocal_rank_fusion


def test_rrf_rewards_items_found_by_both_lists():
    scores = reciprocal_rank_fusion([(1.0, ["a", "b", "c"]), (1.0, ["c", "d"])])
    assert max(scores, key=scores.get) == "c"


def test_rrf_weight_scales_a_list():
    scores = reciprocal_rank_fusion([(1.0, ["vector_hit"]), (0.1, ["keyword_hit"])])
    assert scores["vector_hit"] > scores["keyword_hit"]
    assert abs(scores["keyword_hit"] - 0.1 / 61) < 1e-12


def test_tsquery_ors_words_and_drops_filler():
    assert keyword_tsquery(["dark", "funny", "revenge", "movie"]) == "dark | funny | revenge"
    assert keyword_tsquery(["something", "like", "movie"]) is None


def test_tsquery_skips_tokens_that_would_break_to_tsquery():
    assert keyword_tsquery(["slow-burn", "thriller"]) == "thriller"
