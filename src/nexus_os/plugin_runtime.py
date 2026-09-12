"""Capability adapter for no-host-import WebAssembly RAD plugins."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import wasmtime

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect
from nexus_os.plugins import PluginStore
from nexus_os.qualification import CapabilityQualification, CapabilityState

_MAX_INPUT = 1_000_000
_MAX_OUTPUT = 1_000_000
_PAGE_BYTES = 65_536


class PluginRuntimeError(ValueError):
    """Safe plugin activation, ABI, resource, or result rejection."""


class WasmPluginAdapter:
    """Run one enabled, qualified plugin without WASI or host imports."""

    def __init__(self, store: PluginStore, plugin_id: str, version: str) -> None:
        record = store.get(plugin_id, version)
        manifest = dict(store.manifest(plugin_id, version))
        if record.state != "ENABLED":
            raise PluginRuntimeError("plugin must be enabled before activation")
        if record.permissions:
            raise PluginRuntimeError("wasm-v1 runtime permits no host permissions")
        if not manifest["qualification"]["required"] or record.qualification_digest is None:
            raise PluginRuntimeError("plugin runtime requires qualification binding")
        capabilities = manifest["capabilities"]
        if len(capabilities) != 1:
            raise PluginRuntimeError("wasm-v1 runtime requires exactly one capability")
        self._capability_id, self._capability_version = capabilities[0].rsplit("@", 1)
        self._operations = tuple(manifest["runtime"]["operations"])
        self._max_fuel = int(manifest["runtime"]["max_fuel"])
        self._max_memory_pages = int(manifest["runtime"]["max_memory_pages"])
        self._qualification = _qualification(
            record.payload_path.parent / "qualification.json",
            record.qualification_digest,
            plugin_id=plugin_id,
            plugin_version=version,
            capability_id=self._capability_id,
            capability_version=self._capability_version,
        )
        try:
            module_bytes = record.payload_path.read_bytes()
            configuration = wasmtime.Config()
            configuration.consume_fuel = True
            self._engine = wasmtime.Engine(configuration)
            self._module = wasmtime.Module(self._engine, module_bytes)
        except (OSError, wasmtime.WasmtimeError) as exc:
            raise PluginRuntimeError("plugin WebAssembly module is invalid") from exc
        if self._module.imports:
            raise PluginRuntimeError("plugin WebAssembly host imports are denied")

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            self._capability_id,
            self._capability_version,
            CapabilityKind.ENGINE_OPERATION,
            "Sandboxed signed WebAssembly plugin capability.",
            self._operations,
            frozenset({ActionEffect.READ_ONLY}),
            True,
            NetworkAccess.DENIED,
            True,
            True,
            ResourceLimits(30, self._max_memory_pages * _PAGE_BYTES // (1024 * 1024) + 1),
        )

    def qualification(self) -> CapabilityQualification:
        return self._qualification

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation not in self._operations:
            raise PluginRuntimeError("plugin operation is unsupported")
        try:
            request = json.dumps(
                {"operation": operation, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        except (TypeError, ValueError) as exc:
            raise PluginRuntimeError("plugin request is not canonical JSON") from exc
        if len(request) > _MAX_INPUT:
            raise PluginRuntimeError("plugin request is oversized")
        store = wasmtime.Store(self._engine)
        store.set_fuel(self._max_fuel)
        store.set_limits(memory_size=self._max_memory_pages * _PAGE_BYTES, memories=1)
        try:
            instance = wasmtime.Instance(store, self._module, [])
            exports = instance.exports(store)
            memory = exports["memory"]
            allocate = exports["alloc"]
            handle = exports["handle"]
            if (
                not isinstance(memory, wasmtime.Memory)
                or not isinstance(allocate, wasmtime.Func)
                or not isinstance(handle, wasmtime.Func)
            ):
                raise PluginRuntimeError("plugin WebAssembly ABI exports are invalid")
            pointer = allocate(store, len(request))
            if not isinstance(pointer, int) or pointer < 0:
                raise PluginRuntimeError("plugin input pointer is invalid")
            if pointer + len(request) > memory.data_len(store):
                raise PluginRuntimeError("plugin input exceeds linear memory")
            memory.write(store, request, pointer)
            packed = handle(store, pointer, len(request))
            if not isinstance(packed, int):
                raise PluginRuntimeError("plugin output descriptor is invalid")
            output_pointer = (packed >> 32) & 0xFFFFFFFF
            output_length = packed & 0xFFFFFFFF
            if output_length > _MAX_OUTPUT or output_pointer + output_length > memory.data_len(
                store
            ):
                raise PluginRuntimeError("plugin output exceeds bounded memory")
            raw = bytes(memory.read(store, output_pointer, output_pointer + output_length))
            result = json.loads(raw, object_pairs_hook=_unique)
        except PluginRuntimeError:
            raise
        except (
            wasmtime.Trap,
            wasmtime.WasmtimeError,
            KeyError,
            TypeError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise PluginRuntimeError("plugin execution failed safely") from exc
        if not isinstance(result, dict):
            raise PluginRuntimeError("plugin result must be a JSON object")
        return cast(Mapping[str, Any], result)


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PluginRuntimeError("plugin result contains duplicate JSON keys")
        result[key] = value
    return result


def _qualification(
    path: Any,
    expected_digest: str | None,
    *,
    plugin_id: str,
    plugin_version: str,
    capability_id: str,
    capability_version: str,
) -> CapabilityQualification:
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_INPUT or _digest_bytes(raw) != expected_digest:
            raise PluginRuntimeError("plugin qualification integrity is invalid")
        document = json.loads(raw, object_pairs_hook=_unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PluginRuntimeError("plugin qualification could not be read") from exc
    fields = {
        "schema_version",
        "plugin_id",
        "plugin_version",
        "capability_id",
        "capability_version",
        "runtime_kind",
        "outcome",
        "evaluated_at",
        "expires_at",
        "benchmark_digest",
        "limitations",
        "attestation_digest",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise PluginRuntimeError("plugin qualification fields are invalid")
    unsigned = {key: value for key, value in document.items() if key != "attestation_digest"}
    if (
        document["schema_version"] != "1.0"
        or document["plugin_id"] != plugin_id
        or document["plugin_version"] != plugin_version
        or document["capability_id"] != capability_id
        or document["capability_version"] != capability_version
        or document["runtime_kind"] != "wasm-v1"
        or document["outcome"] != "QUALIFIED"
        or document["attestation_digest"] != _digest_json(unsigned)
        or not isinstance(document["benchmark_digest"], str)
        or not document["benchmark_digest"].startswith("sha256:")
        or not isinstance(document["limitations"], list)
        or any(not isinstance(item, str) for item in document["limitations"])
    ):
        raise PluginRuntimeError("plugin qualification binding is invalid")
    try:
        evaluated = _time(document["evaluated_at"])
        expires = _time(document["expires_at"])
    except (TypeError, ValueError) as exc:
        raise PluginRuntimeError("plugin qualification time is invalid") from exc
    if not evaluated < expires:
        raise PluginRuntimeError("plugin qualification validity is invalid")
    return CapabilityQualification(
        capability_id,
        CapabilityState.QUALIFIED,
        "plugin-wasm-1.0",
        evaluated,
        (),
        tuple(document["limitations"]),
        expires,
    )


def _time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError
    return parsed


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return _digest_bytes(raw)
