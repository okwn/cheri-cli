"""Deployment metadata discovery for Cheri."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeploymentInfo:
    api_url: str
    custom_domain: str
    kv_binding: str
    kv_id: str
    r2_binding: str
    bucket_name: str
    wrangler_information_path: str = ""
    wrangler_toml_path: str = ""
    notes: tuple[str, ...] = ()


EMBEDDED_DEPLOYMENT = DeploymentInfo(
    api_url="https://cheri.parapanteri.com",
    custom_domain="cheri.parapanteri.com",
    kv_binding="HERMES_KV",
    kv_id="00000000000000000000000000000000",
    r2_binding="HERMES_BUCKET",
    bucket_name="cheri-files",
    notes=("Embedded public defaults for the published repository.",),
)


def _repo_roots() -> list[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []
    for raw in (
        os.environ.get("CHERI_REPO_ROOT"),
        str(Path.cwd()),
        str(Path(__file__).resolve()),
    ):
        if not raw:
            continue
        path = Path(raw).resolve()
        lineage = [path, *path.parents[:6]]
        for candidate in lineage:
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _find_file(*names: str) -> Path | None:
    for root in _repo_roots():
        for name in names:
            candidate = root / name
            if candidate.exists():
                return candidate
    return None


def _parse_wrangler_information(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    parsed = {
        "api_url": "",
        "custom_domain": "",
        "kv_binding": "",
        "kv_id": "",
        "r2_binding": "",
        "bucket_name": "",
    }

    def find(pattern: str) -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""

    parsed["api_url"] = find(r"^Worker API base URL:\s*(https?://\S+)\s*$")
    parsed["custom_domain"] = find(r"^Custom domain:\s*([A-Za-z0-9.-]+)\s*$")
    parsed["kv_binding"] = find(r"^KV binding:\s*([A-Za-z0-9_-]+)\s*$")
    parsed["kv_id"] = find(r"^KV id:\s*([a-f0-9]+)\s*$")
    parsed["r2_binding"] = find(r"^R2 binding:\s*([A-Za-z0-9_-]+)\s*$")
    parsed["bucket_name"] = find(r"^R2 bucket:\s*([A-Za-z0-9._-]+)\s*$")

    # Fallback for older raw Wrangler output snippets.
    bindings = re.findall(r'^\s*binding\s*=\s*"([^"]+)"\s*$', text, flags=re.MULTILINE)
    if bindings and not parsed["kv_binding"]:
        parsed["kv_binding"] = bindings[0]
    if len(bindings) > 1 and not parsed["r2_binding"]:
        parsed["r2_binding"] = bindings[1]
    if not parsed["kv_id"]:
        parsed["kv_id"] = find(r'^\s*id\s*=\s*"([a-f0-9]+)"\s*$')
    if not parsed["bucket_name"]:
        parsed["bucket_name"] = find(r'^\s*bucket_name\s*=\s*"([^"]+)"\s*$')

    if parsed["custom_domain"] and not parsed["api_url"]:
        parsed["api_url"] = f"https://{parsed['custom_domain']}"
    return parsed


def _parse_wrangler_toml(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    parsed = {
        "custom_domain": "",
        "api_url": "",
        "kv_binding": "",
        "kv_id": "",
        "r2_binding": "",
        "bucket_name": "",
    }

    def block_value(block_name: str, field_name: str) -> str:
        pattern = rf"\[\[{re.escape(block_name)}\]\](.*?)(?=\n\[\[|\n\[|$)"
        block = re.search(pattern, text, flags=re.DOTALL)
        if not block:
            return ""
        field = re.search(rf'^\s*{re.escape(field_name)}\s*=\s*"([^"]+)"\s*$', block.group(1), flags=re.MULTILINE)
        return field.group(1).strip() if field else ""

    parsed["kv_binding"] = block_value("kv_namespaces", "binding")
    parsed["kv_id"] = block_value("kv_namespaces", "id")
    parsed["r2_binding"] = block_value("r2_buckets", "binding")
    parsed["bucket_name"] = block_value("r2_buckets", "bucket_name")
    parsed["custom_domain"] = block_value("routes", "pattern")
    if parsed["custom_domain"]:
        parsed["api_url"] = f"https://{parsed['custom_domain']}"
    return parsed


def load_deployment_info() -> DeploymentInfo:
    payload = {
        "api_url": EMBEDDED_DEPLOYMENT.api_url,
        "custom_domain": EMBEDDED_DEPLOYMENT.custom_domain,
        "kv_binding": EMBEDDED_DEPLOYMENT.kv_binding,
        "kv_id": EMBEDDED_DEPLOYMENT.kv_id,
        "r2_binding": EMBEDDED_DEPLOYMENT.r2_binding,
        "bucket_name": EMBEDDED_DEPLOYMENT.bucket_name,
    }
    notes = list(EMBEDDED_DEPLOYMENT.notes)
    wrangler_information_path = ""
    wrangler_toml_path = ""

    wrangler_information = _find_file("wrangler_information", "wrangler_information.txt")
    if wrangler_information:
        parsed = _parse_wrangler_information(wrangler_information)
        wrangler_information_path = str(wrangler_information)
        for key, value in parsed.items():
            if value:
                payload[key] = value

    wrangler_toml = _find_file("wrangler.toml")
    if wrangler_toml:
        parsed = _parse_wrangler_toml(wrangler_toml)
        wrangler_toml_path = str(wrangler_toml)
        for key, value in parsed.items():
            if value:
                payload[key] = value

    if payload["custom_domain"] and not payload["api_url"]:
        payload["api_url"] = f"https://{payload['custom_domain']}"

    if wrangler_information_path and wrangler_toml_path:
        info_values = _parse_wrangler_information(Path(wrangler_information_path))
        toml_values = _parse_wrangler_toml(Path(wrangler_toml_path))
        if info_values.get("kv_binding") and toml_values.get("kv_binding") and info_values["kv_binding"] != toml_values["kv_binding"]:
            notes.append(
                f"Normalized KV binding from {info_values['kv_binding']} to {toml_values['kv_binding']} using wrangler.toml."
            )
        if info_values.get("r2_binding") and toml_values.get("r2_binding") and info_values["r2_binding"] != toml_values["r2_binding"]:
            notes.append(
                f"Normalized R2 binding from {info_values['r2_binding']} to {toml_values['r2_binding']} using wrangler.toml."
            )

    return DeploymentInfo(
        api_url=payload["api_url"],
        custom_domain=payload["custom_domain"],
        kv_binding=payload["kv_binding"],
        kv_id=payload["kv_id"],
        r2_binding=payload["r2_binding"],
        bucket_name=payload["bucket_name"],
        wrangler_information_path=wrangler_information_path,
        wrangler_toml_path=wrangler_toml_path,
        notes=tuple(dict.fromkeys(notes)),
    )
