"""Offline compressor comparison helpers for structured compile research."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    output_type: str
    original_chars: int
    compressed_chars: int
    original_token_estimate: int
    compressed_token_estimate: int
    compression_ratio: float


@dataclass(frozen=True)
class TextBlockCorpusCase:
    label: str
    text: str
    max_chars: int


@dataclass(frozen=True)
class CompressorCorpusCaseSummary:
    label: str
    changed: bool
    reason: str
    output_type: str
    original_token_estimate: int
    compressed_token_estimate: int
    saved_token_estimate: int
    compression_ratio: float


@dataclass(frozen=True)
class CompressorCorpusSummary:
    adapter_name: str
    case_count: int
    changed_count: int
    original_token_estimate: int
    compressed_token_estimate: int
    saved_token_estimate: int
    compression_ratio: float
    case_summaries: List[CompressorCorpusCaseSummary] = field(default_factory=list)


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
                output_type=compressed.output_type,
                original_chars=compressed.original_chars,
                compressed_chars=compressed.compressed_chars,
                original_token_estimate=before_tokens,
                compressed_token_estimate=after_tokens,
                compression_ratio=compression_ratio(before_tokens, after_tokens),
            )
        )
    return results


def evaluate_text_block_corpus(
    cases: Iterable[TextBlockCorpusCase],
    *,
    adapters: Iterable[TextBlockCompressorAdapter] = (DeterministicBaselineAdapter(),),
) -> List[CompressorCorpusSummary]:
    """Summarize offline candidate performance over anonymized text blocks."""
    case_list = list(cases)
    summaries: List[CompressorCorpusSummary] = []
    for adapter in adapters:
        changed_count = 0
        original_total = 0
        compressed_total = 0
        case_summaries: List[CompressorCorpusCaseSummary] = []
        for case in case_list:
            [comparison] = compare_text_block_compressors(
                case.text,
                max_chars=case.max_chars,
                adapters=[adapter],
            )
            if comparison.changed:
                changed_count += 1
            original_total += comparison.original_token_estimate
            compressed_total += comparison.compressed_token_estimate
            case_summaries.append(
                CompressorCorpusCaseSummary(
                    label=case.label,
                    changed=comparison.changed,
                    reason=comparison.reason,
                    output_type=comparison.output_type,
                    original_token_estimate=comparison.original_token_estimate,
                    compressed_token_estimate=comparison.compressed_token_estimate,
                    saved_token_estimate=max(
                        0,
                        comparison.original_token_estimate - comparison.compressed_token_estimate,
                    ),
                    compression_ratio=comparison.compression_ratio,
                )
            )
        saved_total = max(0, original_total - compressed_total)
        summaries.append(
            CompressorCorpusSummary(
                adapter_name=adapter.name,
                case_count=len(case_list),
                changed_count=changed_count,
                original_token_estimate=original_total,
                compressed_token_estimate=compressed_total,
                saved_token_estimate=saved_total,
                compression_ratio=compression_ratio(original_total, compressed_total),
                case_summaries=case_summaries,
            )
        )
    return summaries
