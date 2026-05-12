"""Lightweight token estimates for structured compile."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import re
from typing import Any, Dict, Optional


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


@dataclass(frozen=True)
class TokenEstimate:
    tokens: int
    estimator_name: str
    estimator_confidence: str


def estimate_text_tokens(text: str, *, model: Optional[str] = None) -> int:
    return estimate_text_tokens_detailed(text, model=model).tokens


def estimate_text_tokens_detailed(text: str, *, model: Optional[str] = None) -> TokenEstimate:
    source = str(text or "")
    tiktoken_estimate = _estimate_with_tiktoken(source, model=model)
    if tiktoken_estimate is not None:
        return tiktoken_estimate
    return _estimate_with_mixed_script_heuristic(source)


def estimate_payload_tokens(payload: Dict[str, Any], *, model: Optional[str] = None) -> int:
    return estimate_payload_tokens_detailed(payload, model=model).tokens


def estimate_payload_tokens_detailed(payload: Dict[str, Any], *, model: Optional[str] = None) -> TokenEstimate:
    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        serialized = str(payload)
    estimate = estimate_text_tokens_detailed(serialized, model=model or _payload_model(payload))
    return TokenEstimate(
        tokens=max(1, estimate.tokens),
        estimator_name=estimate.estimator_name,
        estimator_confidence=estimate.estimator_confidence,
    )


def compression_ratio(before_tokens: int, after_tokens: int) -> float:
    if before_tokens <= 0 or after_tokens <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (after_tokens / before_tokens)))


def _payload_model(payload: Dict[str, Any]) -> Optional[str]:
    model = payload.get("model") if isinstance(payload, dict) else None
    return str(model) if model else None


def _estimate_with_tiktoken(text: str, *, model: Optional[str]) -> Optional[TokenEstimate]:
    model_name = str(model or "").strip()
    if not model_name:
        return None
    try:
        tiktoken = importlib.import_module("tiktoken")
    except Exception:
        return None
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None
    try:
        return TokenEstimate(
            tokens=len(encoding.encode(text or "")),
            estimator_name="tiktoken",
            estimator_confidence="high",
        )
    except Exception:
        return None


def _estimate_with_mixed_script_heuristic(text: str) -> TokenEstimate:
    source = str(text or "")
    if not source:
        return TokenEstimate(tokens=0, estimator_name="mixed_script_heuristic_v1", estimator_confidence="medium")

    cjk_count = len(_CJK_RE.findall(source))
    non_cjk = _CJK_RE.sub("", source)
    non_space = len("".join(non_cjk.split()))
    ascii_like_tokens = int(non_space / 4)
    punctuation_tokens = int(sum(1 for char in non_cjk if not char.isalnum() and not char.isspace()) / 8)
    return TokenEstimate(
        tokens=max(1, cjk_count + ascii_like_tokens + punctuation_tokens),
        estimator_name="mixed_script_heuristic_v1",
        estimator_confidence="medium",
    )
