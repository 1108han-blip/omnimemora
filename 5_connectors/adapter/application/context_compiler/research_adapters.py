"""Offline compressor comparison helpers for structured compile research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol

from .compressors import CompressionResult, compress_tool_result_text
from .metrics import compression_ratio, estimate_text_tokens


class TextBlockCompressorAdapter(Protocol):
    """Protocol for offline text-block compressor experiments."""

    name: str

    def compress(self, text: str, *, max_chars: int) -> CompressionResult:
        ...


@dataclass(frozen=True)
class CompressorComparison:
    adapter_name: str
    changed: bool
    reason: str
    original_chars: int
    compressed_chars: int
    original_token_estimate: int
    compressed_token_estimate: int
    compression_ratio: float


class DeterministicBaselineAdapter:
    name = "deterministic_extract"

    def compress(self, text: str, *, max_chars: int) -> CompressionResult:
        return compress_tool_result_text(text, max_chars=max_chars)


def compare_text_block_compressors(
    text: str,
    *,
    max_chars: int,
    adapters: Iterable[TextBlockCompressorAdapter] = (DeterministicBaselineAdapter(),),
) -> List[CompressorComparison]:
    """Compare offline compressor candidates without touching product hot paths."""
    source = str(text or "")
    before_tokens = estimate_text_tokens(source)
    results: List[CompressorComparison] = []
    for adapter in adapters:
        compressed = adapter.compress(source, max_chars=max_chars)
        after_tokens = estimate_text_tokens(compressed.text)
        results.append(
            CompressorComparison(
                adapter_name=adapter.name,
                changed=compressed.changed,
                reason=compressed.reason,
                original_chars=compressed.original_chars,
                compressed_chars=compressed.compressed_chars,
                original_token_estimate=before_tokens,
                compressed_token_estimate=after_tokens,
                compression_ratio=compression_ratio(before_tokens, after_tokens),
            )
        )
    return results
