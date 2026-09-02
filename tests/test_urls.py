import pytest

from runrepro.errors import InvalidRunURLError
from runrepro.urls import parse_run_url


@pytest.mark.parametrize(
    ("url", "attempt"),
    [
        ("https://github.com/acme/widgets/actions/runs/424242", None),
        ("https://github.com/acme/widgets/actions/runs/424242/attempts/2", 2),
        ("https://github.com/acme/widgets/actions/runs/424242?check_suite_focus=true", None),
    ],
)
def test_parse_run_url_accepts_canonical_variants(url: str, attempt: int | None) -> None:
    parsed = parse_run_url(url)

    assert parsed.owner == "acme"
    assert parsed.repository == "widgets"
    assert parsed.run_id == 424242
    assert parsed.attempt == attempt


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/acme/widgets/actions/runs/1",
        "https://github.com/acme/widgets/actions/workflows/ci.yml",
        "https://github.com/acme/widgets/actions/runs/not-a-number",
        "https://github.com/acme/widgets/actions/runs/0",
        "github.com/acme/widgets/actions/runs/42",
    ],
)
def test_parse_run_url_rejects_non_run_or_unsafe_urls(url: str) -> None:
    with pytest.raises(InvalidRunURLError):
        parse_run_url(url)

