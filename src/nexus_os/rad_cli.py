"""RAD Agent setup, diagnostics, and local server command."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from nexus_os.agent_model_config import AgentModelConfigError, load_agent_model_config
from nexus_os.agent_server_cli import run as run_server

_DEFAULT_ENDPOINTS = (
    "http://127.0.0.1:11434/v1",
    "http://127.0.0.1:1234/v1",
    "http://127.0.0.1:8080/v1",
)
_SETTINGS = "settings.json"
_CONFIG = "models.yaml"
_PASSWORD = "operator-password"
_MIN_PASSWORD = 12


class RadCliError(ValueError):
    """Safe local setup or diagnostic failure."""


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    base_url: str
    models: tuple[str, ...]


Probe = Callable[[str, int], tuple[str, ...]]
PasswordReader = Callable[[str], str]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="rad",
        description="Configure, diagnose, and run RAD Agent locally",
    )
    commands = result.add_subparsers(dest="command", required=True)

    setup = commands.add_parser("setup", help="Create local RAD Agent configuration")
    setup.add_argument("--config-dir", type=Path, default=Path(".rad-agent"))
    setup.add_argument("--base-url")
    setup.add_argument("--model")
    setup.add_argument(
        "--mode", choices=("development", "qualified"), default="development"
    )
    setup.add_argument("--attestation", type=Path)
    setup.add_argument("--credential-ref")
    setup.add_argument("--force", action="store_true")
    setup.add_argument("--timeout-seconds", type=int, default=5)

    doctor = commands.add_parser("doctor", help="Check local RAD Agent readiness")
    doctor.add_argument("--config-dir", type=Path, default=Path(".rad-agent"))
    doctor.add_argument("--json", action="store_true", dest="as_json")

    serve = commands.add_parser("serve", help="Start the local RAD Agent application")
    serve.add_argument("--config-dir", type=Path, default=Path(".rad-agent"))
    serve.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return result


def probe_models(base_url: str, timeout_seconds: int) -> tuple[str, ...]:
    _loopback_url(base_url)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if response.status != 200:
                return ()
            payload = response.read(1024 * 1024 + 1)
    except (OSError, TimeoutError, urllib.error.URLError):
        return ()
    if len(payload) > 1024 * 1024:
        return ()
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        return ()
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        return ()
    models: list[str] = []
    for item in value["data"]:
        identifier = item.get("id") if isinstance(item, dict) else None
        if isinstance(identifier, str) and 1 <= len(identifier) <= 200:
            models.append(identifier)
    return tuple(sorted(set(models)))


def detect_models(
    *,
    base_url: str | None,
    timeout_seconds: int,
    probe: Probe = probe_models,
) -> tuple[ModelEndpoint, ...]:
    candidates = (base_url,) if base_url is not None else _DEFAULT_ENDPOINTS
    found = []
    for candidate in candidates:
        _loopback_url(candidate)
        models = probe(candidate, timeout_seconds)
        if models:
            found.append(ModelEndpoint(candidate, models))
    return tuple(found)


def setup_local(
    values: argparse.Namespace,
    *,
    probe: Probe = probe_models,
    password_reader: PasswordReader = getpass.getpass,
) -> dict[str, Any]:
    root = values.config_dir.resolve()
    settings_path = root / _SETTINGS
    config_path = root / _CONFIG
    password_path = root / _PASSWORD
    if not 1 <= values.timeout_seconds <= 60:
        raise RadCliError("timeout must be from 1 to 60 seconds")
    if settings_path.exists() and not values.force:
        raise RadCliError("configuration already exists; use --force to replace it")
    endpoints = detect_models(
        base_url=values.base_url,
        timeout_seconds=values.timeout_seconds,
        probe=probe,
    )
    if not endpoints:
        raise RadCliError("no compatible loopback model endpoint was detected")
    if len(endpoints) != 1:
        raise RadCliError(
            "multiple model endpoints detected; select one with --base-url"
        )
    endpoint = endpoints[0]
    model = values.model
    if model is None:
        if len(endpoint.models) != 1:
            raise RadCliError("multiple models detected; select one with --model")
        model = endpoint.models[0]
    if model not in endpoint.models:
        raise RadCliError("selected model was not reported by the endpoint")
    if values.mode == "qualified" and values.attestation is None:
        raise RadCliError("qualified mode requires --attestation")
    credential = values.credential_ref
    if credential is not None and not credential.startswith(
        ("env:", "file:", "keyring:")
    ):
        raise RadCliError(
            "credential must be an opaque env:, file:, or keyring: reference"
        )

    password = password_reader("Create an operator password (12+ characters): ")
    confirmation = password_reader("Confirm the operator password: ")
    if password != confirmation or not _MIN_PASSWORD <= len(password) <= 1024:
        raise RadCliError(
            "operator passwords do not match or are outside allowed length"
        )

    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    profile: dict[str, Any] = {
        "type": "local_openai",
        "base_url": endpoint.base_url,
        "model": model,
        "adapter_version": "1.0",
        "timeout_seconds": values.timeout_seconds,
    }
    if credential is not None:
        profile["credential"] = credential
    document = {
        "schema_version": "1.0",
        "selected": "local_default",
        "profiles": {"local_default": profile},
    }
    config_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    os.chmod(config_path, 0o600)
    password_path.write_text(password + "\n", encoding="utf-8")
    os.chmod(password_path, 0o600)
    settings: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": values.mode,
        "model_config": str(config_path),
        "password_file": str(password_path),
        "state_dir": str(root / "state"),
    }
    if values.attestation is not None:
        settings["attestation"] = str(values.attestation.resolve())
    settings_path.write_text(
        json.dumps(settings, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(settings_path, 0o600)
    load_agent_model_config(config_path)
    return {
        "status": "configured",
        "mode": values.mode,
        "model": model,
        "base_url": endpoint.base_url,
        "config_dir": str(root),
        "qualified": values.mode == "qualified",
    }


def doctor_local(
    config_dir: Path,
    *,
    probe: Probe = probe_models,
) -> tuple[bool, list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    try:
        settings = _load_settings(config_dir)
        checks.append(_check("settings", True, "settings loaded"))
    except RadCliError as exc:
        return False, [_check("settings", False, str(exc))]
    mode = settings["mode"]
    config_path = Path(settings["model_config"])
    password_path = Path(settings["password_file"])
    try:
        configuration = load_agent_model_config(config_path)
        profile = configuration.profiles[configuration.selected]
        checks.append(_check("model_config", True, "model configuration is valid"))
    except (AgentModelConfigError, OSError) as exc:
        checks.append(_check("model_config", False, str(exc)))
        return False, checks
    private = _private_regular(password_path)
    checks.append(
        _check(
            "password_file",
            private,
            "password file is private"
            if private
            else "password file must be owner-only",
        )
    )
    models = probe(profile.base_url, profile.timeout_seconds)
    available = profile.model in models
    checks.append(
        _check(
            "model_endpoint",
            available,
            "selected model is available"
            if available
            else "selected model is unavailable",
        )
    )
    if mode == "qualified":
        attestation = settings.get("attestation")
        present = isinstance(attestation, str) and Path(attestation).is_file()
        checks.append(
            _check(
                "qualification",
                present,
                "attestation file is present"
                if present
                else "qualified mode needs an attestation",
            )
        )
    else:
        checks.append(
            {
                "name": "qualification",
                "status": "warning",
                "message": "UNQUALIFIED DEVELOPMENT MODE: planning/review only; no execution",
            }
        )
    return all(item["status"] != "fail" for item in checks), checks


def serve_local(values: argparse.Namespace) -> int:
    settings = _load_settings(values.config_dir)
    mode = settings["mode"]
    os.environ["RAD_AGENT_MODE"] = mode
    os.environ["RAD_AGENT_MODEL_CONFIG"] = settings["model_config"]
    attestation = settings.get("attestation")
    if isinstance(attestation, str):
        os.environ["RAD_AGENT_MODEL_ATTESTATION"] = attestation
    if mode == "development":
        print(
            "WARNING: UNQUALIFIED DEVELOPMENT MODE — planning/review only; "
            "no runtime execution is enabled.",
            file=sys.stderr,
            flush=True,
        )
    return run_server(
        [
            "--state-dir",
            settings["state_dir"],
            "--password-file",
            settings["password_file"],
            "--host",
            values.host,
            "--port",
            str(values.port),
        ]
    )


def run(
    arguments: Sequence[str] | None = None,
    *,
    probe: Probe = probe_models,
    password_reader: PasswordReader = getpass.getpass,
) -> int:
    try:
        values = parser().parse_args(arguments)
        if values.command == "setup":
            _emit(setup_local(values, probe=probe, password_reader=password_reader))
            return 0
        if values.command == "doctor":
            healthy, checks = doctor_local(values.config_dir, probe=probe)
            if values.as_json:
                _emit({"healthy": healthy, "checks": checks})
            else:
                for item in checks:
                    print(
                        f"[{item['status'].upper()}] {item['name']}: {item['message']}"
                    )
            return 0 if healthy else 2
        if values.command == "serve":
            return serve_local(values)
        raise RadCliError("unsupported RAD command")
    except (RadCliError, AgentModelConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run())


def _load_settings(config_dir: Path) -> dict[str, Any]:
    path = config_dir.resolve() / _SETTINGS
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RadCliError("RAD Agent settings could not be loaded") from exc
    required = {
        "schema_version",
        "mode",
        "model_config",
        "password_file",
        "state_dir",
    }
    if (
        not isinstance(value, dict)
        or not required <= set(value)
        or set(value) - (required | {"attestation"})
        or value["schema_version"] != "1.0"
        or value["mode"] not in {"development", "qualified"}
        or any(
            not isinstance(value[key], str)
            for key in required - {"schema_version", "mode"}
        )
        or ("attestation" in value and not isinstance(value["attestation"], str))
    ):
        raise RadCliError("RAD Agent settings are invalid")
    return value


def _loopback_url(value: str) -> None:
    try:
        endpoint = urlsplit(value)
        port = endpoint.port
    except (TypeError, ValueError) as exc:
        raise RadCliError("model endpoint is invalid") from exc
    if (
        endpoint.scheme not in {"http", "https"}
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port is None
        or endpoint.path.rstrip("/") != "/v1"
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        raise RadCliError("model endpoint must be an explicit loopback /v1 URL")


def _private_regular(path: Path) -> bool:
    try:
        details = path.stat()
    except OSError:
        return False
    return stat.S_ISREG(details.st_mode) and not details.st_mode & 0o077


def _check(name: str, passed: bool, message: str) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail", "message": message}


def _emit(value: object) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":  # pragma: no cover
    main()
