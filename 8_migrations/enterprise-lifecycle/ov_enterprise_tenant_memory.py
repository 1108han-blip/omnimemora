"""Tenant memory helpers built on top of the current single-agent adapter model."""

from __future__ import annotations

import re
import uuid
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_MEMORY_ADAPTER_DIR,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_VIKING_API_KEY,
    DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    extract_request_id,
    http_json_with_meta,
)


def sanitize_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip())
    return normalized.strip(".-") or "unknown"


def derived_agent_id(tenant_id: str, agent_id: str | None = None) -> str:
    base_agent = sanitize_segment(agent_id or DEFAULT_EXPECTED_AGENT_ID)
    return f"{sanitize_segment(tenant_id)}__{base_agent}"


def tenant_namespace_uri(
    tenant_id: str,
    agent_id: str | None = None,
    *,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
) -> str:
    root = (namespace_root or DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT).rstrip("/")
    return f"{root}/{derived_agent_id(tenant_id, agent_id)}"


def _viking_headers(api_key: str | None = None) -> dict[str, str] | None:
    resolved = api_key or discover_viking_api_key()
    if resolved:
        return {"X-API-Key": resolved}
    return None


def discover_viking_api_key() -> str | None:
    for candidate in (
        DEFAULT_MEMORY_ADAPTER_DIR / "docker-compose.yml",
        DEFAULT_MEMORY_ADAPTER_DIR / "docker-compose.full.yml",
    ):
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"VIKING_API_KEY(?:=|:\s*)([^\r\n]+)", text)
        if match:
            return match.group(1).strip().strip("'\"")
    return DEFAULT_VIKING_API_KEY or None


def _tree_result_items(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _entry_leaf_name(entry: dict[str, Any]) -> str:
    rel_path = entry.get("rel_path")
    if isinstance(rel_path, str) and rel_path:
        return PurePosixPath(rel_path).name
    return PurePosixPath(str(entry.get("uri") or "")).name


def _entry_is_leaf(entry: dict[str, Any]) -> bool:
    return not bool(entry.get("is_dir"))


def _entry_parent_resource_uri(uri: str) -> str | None:
    if not isinstance(uri, str) or not uri:
        return None
    if "://" not in uri:
        parent = PurePosixPath(uri).parent.as_posix()
        return None if parent in {".", uri} else parent
    scheme, remainder = uri.split("://", 1)
    parts = [part for part in remainder.split("/") if part]
    if len(parts) <= 1:
        return None
    return f"{scheme}://{'/'.join(parts[:-1])}"


def _entry_memory_type(entry: dict[str, Any]) -> str:
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    memory_type = metadata.get("memory_type")
    if isinstance(memory_type, str) and memory_type.strip():
        return memory_type.strip()
    rel_path = entry.get("rel_path")
    if isinstance(rel_path, str) and rel_path.strip():
        parts = PurePosixPath(rel_path).parts
        if parts:
            return parts[0]
    return "short_term"


def _build_target_resource_uri(
    tenant_id: str,
    record: dict[str, Any],
    *,
    agent_id: str | None = None,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
) -> str:
    source_uri = record.get("uri")
    memory_type = sanitize_segment(_entry_memory_type(record))
    tenant_root = tenant_namespace_uri(tenant_id, agent_id, namespace_root=namespace_root)
    if isinstance(source_uri, str) and source_uri.endswith(".md"):
        filename = PurePosixPath(source_uri).name
        if filename.startswith("upload_"):
            return f"{tenant_root}/{memory_type}/restore-{uuid.uuid4().hex}.md"
        return f"{tenant_root}/{memory_type}/{filename}"
    return f"{tenant_root}/{memory_type}/mem-{uuid.uuid4().hex}.md"


def _openviking_client(
    *,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    timeout: float = 45.0,
) -> httpx.Client:
    return httpx.Client(
        base_url=openviking_url.rstrip("/"),
        headers=_viking_headers(api_key) or {},
        timeout=timeout,
    )


def _list_resource_tree(
    root_uri: str,
    *,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    status, payload, _meta = http_json_with_meta(
        f"{openviking_url.rstrip('/')}/api/v1/fs/tree?uri={quote(root_uri, safe='')}",
        timeout=timeout,
        headers=_viking_headers(api_key),
    )
    if status in {0, 404}:
        return []
    if status == 500 and isinstance(payload, dict):
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        message = str(error.get("message") or "").lower()
        if "no such directory" in message:
            return []
    if status != 200:
        raise RuntimeError(f"tree_list_failed:{status}")
    entries: list[dict[str, Any]] = []
    for item in _tree_result_items(payload):
        uri = item.get("uri")
        rel_path = item.get("rel_path")
        if not isinstance(uri, str) or not uri:
            continue
        if not isinstance(rel_path, str) or not rel_path:
            rel_path = uri.rsplit("/", 1)[-1]
        if PurePosixPath(rel_path).name.startswith("."):
            continue
        entries.append(
            {
                "uri": uri,
                "rel_path": rel_path,
                "is_dir": bool(item.get("isDir")),
                "abstract": item.get("abstract"),
            }
        )
    return entries


def list_tenant_resource_entries(
    tenant_id: str,
    *,
    agent_id: str | None = None,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    root_uri = tenant_namespace_uri(tenant_id, agent_id, namespace_root=namespace_root)
    queue: list[str] = [root_uri]
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        for entry in _list_resource_tree(current, openviking_url=openviking_url, api_key=api_key, timeout=timeout):
            rel_path = str(entry.get("rel_path") or "")
            uri = str(entry.get("uri") or "")
            if entry.get("is_dir"):
                queue.append(uri)
            if rel_path.endswith(".md"):
                entries.append(entry)
    unique_entries: dict[str, dict[str, Any]] = {}
    for entry in entries:
        uri = str(entry.get("uri") or "")
        if uri:
            unique_entries[uri] = entry
    return sorted(unique_entries.values(), key=lambda item: str(item.get("rel_path") or item.get("uri")))


def list_tenant_resource_uris(
    tenant_id: str,
    *,
    agent_id: str | None = None,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    timeout: float = 20.0,
) -> list[str]:
    return [
        str(item["uri"])
        for item in list_tenant_resource_entries(
            tenant_id,
            agent_id=agent_id,
            openviking_url=openviking_url,
            api_key=api_key,
            namespace_root=namespace_root,
            timeout=timeout,
        )
    ]


def read_raw_memory_resource(
    uri: str,
    *,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    timeout: float = 20.0,
) -> str | None:
    status, payload, _meta = http_json_with_meta(
        f"{openviking_url.rstrip('/')}/api/v1/content/read?uri={quote(uri, safe='')}",
        timeout=timeout,
        headers=_viking_headers(api_key),
    )
    if status in {0, 404}:
        return None
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"content_read_failed:{status}")
    result = payload.get("result")
    return result if isinstance(result, str) else None


def resolve_leaf_resource_uri(
    root_uri: str,
    *,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    timeout: float = 20.0,
) -> str:
    queue: list[str] = [root_uri]
    seen: set[str] = set()
    leaf_entries: list[dict[str, Any]] = []
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        for entry in _list_resource_tree(current, openviking_url=openviking_url, api_key=api_key, timeout=timeout):
            uri = str(entry.get("uri") or "")
            if entry.get("is_dir"):
                queue.append(uri)
            else:
                leaf_entries.append(entry)
    if not leaf_entries:
        return root_uri
    chosen = sorted(leaf_entries, key=lambda item: str(item.get("rel_path") or item.get("uri")))[-1]
    return str(chosen.get("uri") or root_uri)


def write_raw_memory_resource(
    raw_content: str,
    *,
    target_uri: str,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    timeout: float = 45.0,
    reason: str = "tenant-import",
    instruction: str = "Restore tenant memory record from a tenant snapshot package.",
) -> dict[str, Any]:
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError("raw_content is required")
    if not isinstance(target_uri, str) or not target_uri.strip():
        raise ValueError("target_uri is required")
    with _openviking_client(openviking_url=openviking_url, api_key=api_key, timeout=timeout) as client:
        upload_response = client.post(
            "/api/v1/resources/temp_upload",
            files={"file": ("memory.md", raw_content.encode("utf-8"), "text/markdown")},
        )
        upload_response.raise_for_status()
        upload_payload = upload_response.json() if upload_response.content else {}
        result = upload_payload.get("result") if isinstance(upload_payload, dict) else {}
        temp_path = result.get("temp_path") if isinstance(result, dict) else None
        if not isinstance(temp_path, str) or not temp_path:
            raise RuntimeError("temp_upload_missing_temp_path")

        commit_response = client.post(
            "/api/v1/resources",
            json={
                "temp_path": temp_path,
                "to": target_uri,
                "reason": reason,
                "instruction": instruction,
                "wait": True,
            },
        )
        commit_response.raise_for_status()
        commit_payload = commit_response.json() if commit_response.content else {}
        commit_result = commit_payload.get("result") if isinstance(commit_payload, dict) else {}
        root_uri = commit_result.get("root_uri") if isinstance(commit_result, dict) else None
        if not isinstance(root_uri, str) or not root_uri:
            root_uri = target_uri
        stored_uri = resolve_leaf_resource_uri(root_uri, openviking_url=openviking_url, api_key=api_key, timeout=timeout)
        return {
            "root_uri": root_uri,
            "uri": stored_uri,
            "payload": commit_payload,
        }


def parse_memory_markdown(raw_content: str | None) -> dict[str, Any]:
    if not isinstance(raw_content, str) or not raw_content.strip():
        return {"raw_content": raw_content, "content": None, "metadata": {}}
    text = raw_content.strip()
    if text.startswith("# Memory"):
        text = text.split("\n", 1)[1].lstrip() if "\n" in text else ""
    if "\n---\n" in text:
        content_text, metadata_block = text.split("\n---\n", 1)
    else:
        content_text, metadata_block = text, ""
    metadata: dict[str, Any] = {}
    for line in metadata_block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped[2:].split(":", 1)
        metadata[key.strip()] = value.strip()
    return {
        "raw_content": raw_content,
        "content": content_text.strip() or None,
        "metadata": metadata,
    }


def export_tenant_memory_records(
    tenant_id: str,
    *,
    agent_id: str | None = None,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    timeout: float = 20.0,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    fallback_records: list[dict[str, Any]] = []
    entries = list_tenant_resource_entries(
        tenant_id,
        agent_id=agent_id,
        openviking_url=openviking_url,
        api_key=api_key,
        namespace_root=namespace_root,
        timeout=timeout,
    )
    for entry in entries:
        uri = str(entry["uri"])
        raw_content = read_raw_memory_resource(uri, openviking_url=openviking_url, api_key=api_key, timeout=timeout)
        parsed = parse_memory_markdown(raw_content)
        record = {
            "tenant_id": tenant_id,
            "derived_agent_id": derived_agent_id(tenant_id, agent_id),
            "uri": uri,
            "source_root_uri": _entry_parent_resource_uri(uri),
            "content": parsed["content"] or entry.get("abstract"),
            "raw_content": parsed["raw_content"],
            "metadata": {
                **parsed["metadata"],
                "rel_path": entry.get("rel_path"),
                "export_abstract_fallback": parsed["content"] is None and bool(entry.get("abstract")),
                "tree_entry_is_dir": entry.get("is_dir"),
            },
        }
        if parsed["content"] is not None:
            records.append(record)
        elif entry.get("abstract"):
            fallback_records.append(record)
    if not records:
        records = fallback_records
    return {
        "tenant_id": tenant_id,
        "derived_agent_id": derived_agent_id(tenant_id, agent_id),
        "namespace_uri": tenant_namespace_uri(tenant_id, agent_id, namespace_root=namespace_root),
        "record_count": len(records),
        "records": records,
    }


def clear_tenant_memory_records(
    records: list[dict[str, Any]],
    *,
    adapter_url: str = DEFAULT_ADAPTER_URL,
    timeout: float = 20.0,
) -> dict[str, Any]:
    deleted: list[str] = []
    failed: list[dict[str, Any]] = []
    delete_targets: set[str] = set()
    for record in records:
        uri = record.get("uri")
        if isinstance(uri, str) and uri:
            delete_targets.add(uri)
            parent_uri = _entry_parent_resource_uri(uri)
            while parent_uri and str(parent_uri).rsplit("/", 1)[-1].endswith(".md"):
                delete_targets.add(parent_uri)
                parent_uri = _entry_parent_resource_uri(parent_uri)
    for uri in sorted(delete_targets, key=lambda item: (item.count("/"), len(item)), reverse=True):
        status, payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/delete",
            method="POST",
            payload={"uri": uri},
            timeout=timeout,
        )
        if status == 200:
            deleted.append(uri)
        else:
            failed.append(
                {
                    "uri": uri,
                    "status_code": status,
                    "payload": payload,
                    "request_id": extract_request_id(meta),
                }
            )
    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "failed": failed,
    }


def import_tenant_memory_records(
    tenant_id: str,
    records: list[dict[str, Any]],
    *,
    agent_id: str | None = None,
    adapter_url: str = DEFAULT_ADAPTER_URL,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    api_key: str | None = DEFAULT_VIKING_API_KEY,
    namespace_root: str = DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    timeout: float = 45.0,
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    imported: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    tenant_agent = derived_agent_id(tenant_id, agent_id)
    for record in records:
        raw_content = record.get("raw_content")
        if isinstance(raw_content, str) and raw_content.strip():
            try:
                target_uri = _build_target_resource_uri(
                    tenant_id,
                    record,
                    agent_id=agent_id,
                    namespace_root=namespace_root,
                )
                direct_result = write_raw_memory_resource(
                    raw_content,
                    target_uri=target_uri,
                    openviking_url=openviking_url,
                    api_key=api_key,
                    timeout=timeout,
                    reason=f"tenant-import:{tenant_id}",
                )
                imported.append(
                    {
                        "source_uri": record.get("uri"),
                        "uri": direct_result.get("uri"),
                        "status": "stored",
                        "request_id": None,
                    }
                )
                continue
            except Exception as exc:  # noqa: BLE001
                failed.append(
                    {
                        "source_uri": record.get("uri"),
                        "status_code": None,
                        "response": f"raw_import_failed:{exc}",
                        "request_id": None,
                    }
                )
                continue
        content = record.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        payload = {
            "agent": tenant_agent,
            "type": metadata.get("type") or "fact",
            "memory_type": metadata.get("memory_type"),
            "content": content,
            "tags": [tenant_id, "tenant-import", *(extra_tags or [])],
        }
        status, response, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/write",
            method="POST",
            payload=payload,
            timeout=timeout,
        )
        request_id = extract_request_id(meta)
        if status == 200 and isinstance(response, dict) and response.get("status") in {"stored", "duplicate"}:
            imported.append(
                {
                    "source_uri": record.get("uri"),
                    "uri": response.get("uri"),
                    "status": response.get("status"),
                    "request_id": request_id,
                }
            )
        else:
            failed.append(
                {
                    "source_uri": record.get("uri"),
                    "status_code": status,
                    "response": response,
                    "request_id": request_id,
                }
            )
    return {
        "tenant_id": tenant_id,
        "derived_agent_id": tenant_agent,
        "imported_count": len(imported),
        "failed_count": len(failed),
        "imported": imported,
        "failed": failed,
    }
