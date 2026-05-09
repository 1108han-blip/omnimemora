import json
import os
import threading
from pathlib import Path
from typing import Dict, Tuple

from .agent_identity import resolve_canonical_agent_id

_lock = threading.Lock()
_agent_modes_cache: Tuple[Dict[str, str], str] = ({}, "off")


def _agent_modes_path() -> Path:
    configured = os.getenv("OMNIMEMORA_AGENT_MODES_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent / "config" / "agent_modes.json"


def reload_agent_modes() -> Tuple[Dict[str, str], str]:
    global _agent_modes_cache
    path = _agent_modes_path()
    with _lock:
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _agent_modes_cache = ({}, "off")
            return _agent_modes_cache

        raw_dict = cfg.get("per_agent_modes", {}) or {}
        canonical_dict = {
            resolve_canonical_agent_id(str(k)): str(v)
            for k, v in raw_dict.items()
        }
        default_mode = str(cfg.get("default_mode", "off") or "off")
        _agent_modes_cache = (canonical_dict, default_mode)
        return _agent_modes_cache


def get_agent_modes_cache() -> Tuple[Dict[str, str], str]:
    global _agent_modes_cache
    if not _agent_modes_cache[0] and _agent_modes_cache[1] == "off":
        return reload_agent_modes()
    return _agent_modes_cache


def save_agent_modes(per_agent_modes: Dict[str, str], default_mode: str = "off") -> Tuple[Dict[str, str], str]:
    path = _agent_modes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical_dict = {
        resolve_canonical_agent_id(k): v
        for k, v in per_agent_modes.items()
    }
    payload = {
        "_comment": "Per-agent routing control for OmniMemora UI. Keys must be canonical_agent_id.",
        "per_agent_modes": canonical_dict,
        "default_mode": default_mode,
    }
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        global _agent_modes_cache
        _agent_modes_cache = (canonical_dict, default_mode)
        return _agent_modes_cache


def routing_enabled(family_id: str) -> bool:
    per_agent, _default_mode = get_agent_modes_cache()
    return per_agent.get(resolve_canonical_agent_id(family_id), "off") == "force_if_possible"


def set_family_routing_enabled(family_id: str, enabled: bool) -> Tuple[Dict[str, str], str]:
    per_agent, default_mode = get_agent_modes_cache()
    updated = dict(per_agent)
    updated[resolve_canonical_agent_id(family_id)] = "force_if_possible" if enabled else "off"
    return save_agent_modes(updated, default_mode=default_mode or "off")
