import importlib
import logging

from .config import config

_internal_transport = importlib.import_module("5_connectors.adapter.internal_transport")


def run_startup_probe() -> None:
    """Log internal transport reachability during adapter startup."""
    if not config.internal_transport.probe_on_startup:
        return

    logger = logging.getLogger("internal_transport")
    probe_services = [
        ("omnimemora_runtime", config.memory_backend.base_url),
    ]
    for service_name, service_url in probe_services:
        try:
            resolved, reason = _internal_transport.resolve_internal_base_url_sync(
                service_name,
                service_url,
                config.internal_transport.loopback_candidates,
            )
            logger.info(
                "[internal_transport] startup probe: "
                f"service={service_name} configured={service_url} "
                f"resolved={resolved} reason={reason}"
            )
        except Exception as exc:
            logger.warning(
                f"[internal_transport] startup probe failed for {service_name}: {exc}"
            )
