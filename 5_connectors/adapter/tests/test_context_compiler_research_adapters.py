import importlib


research = importlib.import_module(
    "5_connectors.adapter.application.context_compiler.research_adapters"
)


def test_deterministic_baseline_adapter_reports_token_saving():
    text = "\n".join([f"src/file_{i}.py:{i}: search result line with details" for i in range(120)])

    [result] = research.compare_text_block_compressors(text, max_chars=900)

    assert result.adapter_name == "deterministic_extract"
    assert result.changed is True
    assert result.compressed_chars < result.original_chars
    assert result.compressed_token_estimate < result.original_token_estimate
    assert result.compression_ratio > 0


def test_research_comparison_can_use_external_candidate_without_hot_path_imports():
    class TinyAdapter:
        name = "tiny_candidate"

        def compress(self, text, *, max_chars):
            return research.CompressionResult(
                text=text[:max_chars],
                changed=True,
                original_chars=len(text),
                compressed_chars=min(len(text), max_chars),
                reason="test_candidate",
            )

    text = "x" * 1000

    [result] = research.compare_text_block_compressors(
        text,
        max_chars=100,
        adapters=[TinyAdapter()],
    )

    assert result.adapter_name == "tiny_candidate"
    assert result.reason == "test_candidate"
    assert result.compressed_chars == 100
