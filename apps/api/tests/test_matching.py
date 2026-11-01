from app.modules.research.matching import fragments, match_any, match_quote, normalize, quote_key

PAGE = """Weekly reports are painful
Our project coordinators spend most of Friday compiling weekly
progress reports from site photos, spreadsheets and emails. It’s entirely manual —
and every project manager complains about it.
"""


def test_exact_match_with_whitespace_and_case_differences() -> None:
    assert match_quote(
        "our project coordinators SPEND most of Friday compiling weekly progress reports", PAGE
    ).found


def test_curly_quotes_and_dashes_normalized() -> None:
    assert match_quote("It's entirely manual - and every project manager complains", PAGE).found


def test_paraphrase_rejected() -> None:
    result = match_quote("Coordinators spend Fridays compiling weekly progress reports", PAGE)
    assert not result.found and "not found" in result.reason


def test_ellipsis_fragments_in_order() -> None:
    assert match_quote("spend most of Friday … every project manager complains", PAGE).found
    assert match_quote("spend most of Friday [...] every project manager complains", PAGE).found
    assert match_quote("spend most of Friday... every project manager complains", PAGE).found


def test_ellipsis_fragments_out_of_order_rejected() -> None:
    result = match_quote("every project manager complains … spend most of Friday", PAGE)
    assert not result.found and "fragment 2 of 2" in result.reason


def test_short_fragment_rejected() -> None:
    result = match_quote("spend most of Friday … it", PAGE)
    assert not result.found and "too short" in result.reason


def test_zero_width_and_nbsp() -> None:
    page = "Reports take four​ hours every week."
    assert match_quote("reports take four hours every week", page).found


def test_match_any_falls_back_to_full_text() -> None:
    main = "Only the article body."
    full = "Navigation ... Only the article body. Footer: we spend hours on weekly reports here."
    assert not match_quote("we spend hours on weekly reports", main).found
    assert match_any("we spend hours on weekly reports", main, full).found
    assert not match_any("never said", main, None).found


def test_quote_key_is_stable() -> None:
    assert quote_key("It’s  Manual … Weekly Reports") == quote_key("it's manual ... weekly reports")
    assert fragments("a sentence here … another one there") == [
        "a sentence here",
        "another one there",
    ]
    assert normalize("  A\n\tB  ") == "a b"
