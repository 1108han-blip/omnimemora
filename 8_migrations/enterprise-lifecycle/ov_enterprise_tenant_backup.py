"""Tenant-scoped backup wrapper backed by the shared context snapshot kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_TENANT_POLICY_PATH,
    DEFAULT_TENANT_REGISTRY_PATH,
    DEFAULT_TENANT_RUNTIME_ROOT,
    DEFAULT_VIKING_API_KEY,
    DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
)
from ov_enterprise_context_snapshot_kernel import context_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking tenant backup")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--instance-root", type=Path, default=DEFAULT_TENANT_RUNTIME_ROOT)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_TENANT_REGISTRY_PATH)
    parser.add_argument("--policy-path", type=Path, default=DEFAULT_TENANT_POLICY_PATH)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--viking-api-key", default=DEFAULT_VIKING_API_KEY)
    parser.add_argument("--namespace-root", default=DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT)
    parser.add_argument("--agent-id", default=DEFAULT_EXPECTED_AGENT_ID)
    parser.add_argument("--snapshot-type", default="manual")
    parser.add_argument("--tag")
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    report = context_backup(
        {
            "context_id": args.tenant,
            "tenant_id": args.tenant,
            "instance_root": args.instance_root,
            "registry_path": args.registry_path,
            "policy_path": args.policy_path,
            "adapter_url": args.adapter_url,
            "openviking_url": args.openviking_url,
            "viking_api_key": args.viking_api_key,
            "namespace_root": args.namespace_root,
            "agent_id": args.agent_id,
            "snapshot_type": args.snapshot_type,
            "tag": args.tag,
            "report_path": args.report_path,
            "execute": args.execute,
        }
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
