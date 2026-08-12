from social_poster.video_editor import wrap_overlay_text


def test_wrap_short_text_stays_one_line():
    assert wrap_overlay_text("short hook") == "short hook"


def test_wrap_long_text_splits_into_multiple_lines():
    text = "this is a much longer overlay hook that should wrap onto multiple lines"
    wrapped = wrap_overlay_text(text)
    lines = wrapped.split("\n")
    assert len(lines) > 1
    assert all(len(line) <= 22 for line in lines)


def test_wrap_collapses_whitespace():
    assert wrap_overlay_text("  hello   world  ") == "hello world"


def test_wrap_empty_text():
    assert wrap_overlay_text("") == ""
    assert wrap_overlay_text("   ") == ""
