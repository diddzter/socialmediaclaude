import pytest

from social_poster.content_analysis import ContentAnalysis, parse_json_block


def test_parse_json_block_plain():
    text = '{"caption": "hi", "hashtags": ["a", "b"], "mood": "chill", "overlay_text": "hook"}'
    parsed = parse_json_block(text)
    assert parsed["caption"] == "hi"
    assert parsed["mood"] == "chill"


def test_parse_json_block_with_markdown_fence():
    text = '```json\n{"caption": "hi", "mood": "chill"}\n```'
    parsed = parse_json_block(text)
    assert parsed["caption"] == "hi"


def test_parse_json_block_with_surrounding_prose():
    text = 'Sure, here you go:\n{"caption": "hi", "mood": "chill"}\nHope that helps!'
    parsed = parse_json_block(text)
    assert parsed["caption"] == "hi"


def test_parse_json_block_raises_without_json():
    with pytest.raises(ValueError):
        parse_json_block("no json here at all")


def test_full_caption_joins_hashtags_with_hash_prefix():
    analysis = ContentAnalysis(caption="Check this out", hashtags=["fun", "ai"], overlay_text="hook", mood="chill")
    assert analysis.full_caption == "Check this out\n\n#fun #ai"
