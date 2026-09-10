"""Bảng giá → cost. Không cần DB / network."""

from app.domain.message import Usage
from app.util import PRICES, cost

_USAGE = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)


def test_known_model_sums_input_and_output_rate():
    in_rate, out_rate = PRICES["openai/gpt-oss-120b"]
    assert cost(_USAGE, "openai/gpt-oss-120b") == round(in_rate + out_rate, 6)


def test_unknown_model_returns_none():
    assert cost(_USAGE, "some-model-chua-co-gia") is None


def test_no_usage_returns_none():
    assert cost(None, "openai/gpt-oss-120b") is None


def test_local_model_priced_zero():
    assert cost(_USAGE, "llama3.2") == 0.0
