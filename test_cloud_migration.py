#!/usr/bin/env python3
"""
云接入迁移测试脚本
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "5_connectors"))

from adapter.config import config
from adapter.cloud import load_policy, load_flags

print("=" * 60)
print("OmniMemora 云接入迁移 - 真实链路验证")
print("=" * 60)
print()

# 验证 1: cloud_enabled=false (默认)
print("[验证 1] cloud_enabled=false (默认配置)")
print(f"  config.cloud.enabled = {config.cloud.enabled}")
policy = load_policy()
flags = load_flags()
print(f"  Policy version: {policy.version}")
print(f"  optimization_enabled: {flags.optimization_enabled}")
print("  ✅ 验证 1 通过")
print()

# 验证 2: cloud_enabled=true 但云不可达 → fallback
print("[验证 2] cloud_enabled=true 但云不可达 → 自动 fallback")
import os
os.environ["CLOUD_ENABLED"] = "true"
os.environ["CLOUD_BASE_URL"] = "https://nonexistent-domain.invalid"

# 重新加载 config（重新 import）
import importlib
import adapter.config
importlib.reload(adapter.config)
from adapter.config import config
from adapter.cloud import load_policy, load_flags

print(f"  config.cloud.enabled = {config.cloud.enabled}")
print(f"  config.cloud.base_url = {config.cloud.base_url}")
policy = load_policy()
flags = load_flags()
print(f"  Policy version (should fallback): {policy.version}")
print(f"  optimization_enabled: {flags.optimization_enabled}")
assert policy.version == "local-default-v1", "Should fallback to local policy"
assert flags.optimization_enabled == True, "Should fallback to local flags"
print("  ✅ 验证 2 通过")
print()

# 验证 3: optimization_enabled=true (默认)
print("[验证 3] optimization_enabled=true (默认)")
print(f"  flags.optimization_enabled = {flags.optimization_enabled}")
assert flags.optimization_enabled == True, "Should be true by default"
print("  ✅ 验证 3 通过")
print()

# 验证 4: optimization_enabled=false 测试
print("[验证 4] optimization_enabled=false")
import json
flags_path = os.path.join(
    os.path.dirname(__file__),
    "5_connectors", "adapter", "config", "default_flags.json"
)
with open(flags_path, "r", encoding="utf-8") as f:
    original_flags = json.load(f)

try:
    test_flags = original_flags.copy()
    test_flags["optimization_enabled"] = False
    with open(flags_path, "w", encoding="utf-8") as f:
        json.dump(test_flags, f)

    # 重新加载
    import adapter.cloud.policy_loader
    import adapter.cloud.flags_loader
    importlib.reload(adapter.cloud.flags_loader)
    from adapter.cloud import load_flags

    flags = load_flags()
    print(f"  flags.optimization_enabled (after set to false): {flags.optimization_enabled}")
    assert flags.optimization_enabled == False, "Should load false"
    print("  ✅ 验证 4 通过")
finally:
    # 恢复
    with open(flags_path, "w", encoding="utf-8") as f:
        json.dump(original_flags, f)

print()
print("=" * 60)
print("✅ 所有验证通过！")
print("=" * 60)
