"""Provider-independent deterministic tabular compute with provenance."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from types import MappingProxyType
from typing import Any, Final

ENGINE: Final = "nexus.compute.stdlib"
ENGINE_VERSION: Final = "1.0"
MAX_INPUT_BYTES: Final = 256 * 1024 * 1024
MAX_ROWS: Final = 1_000_000
MAX_COLUMNS: Final = 1_024
type Scalar = str | int | float | bool | None


class ComputeError(ValueError):
    """Stable failure for invalid or bounded deterministic computation."""


@dataclass(frozen=True, slots=True)
class Provenance:
    engine: str
    version: str
    input_digest: str
    parameters: Mapping[str, Any]
    seed: int | None
    output_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze(self.parameters))


@dataclass(frozen=True, slots=True)
class Table:
    columns: tuple[str, ...]
    types: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]
    digest: str

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class ComputeArtifact:
    operation: str
    value: Any
    provenance: Provenance


class DeterministicCompute:
    """Deterministic calculations over caller-supplied data; performs no I/O."""

    def load_csv(
        self,
        payload: bytes,
        *,
        delimiter: str = ",",
        max_rows: int = MAX_ROWS,
    ) -> ComputeArtifact:
        if not isinstance(payload, bytes) or not payload or len(payload) > MAX_INPUT_BYTES:
            raise ComputeError("CSV payload size is invalid")
        if len(delimiter) != 1 or delimiter in {'"', "\r", "\n"}:
            raise ComputeError("CSV delimiter is invalid")
        if isinstance(max_rows, bool) or not 1 <= max_rows <= MAX_ROWS:
            raise ComputeError("max_rows is invalid")
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ComputeError("CSV payload must be UTF-8") from exc
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        try:
            header = next(reader)
        except (StopIteration, csv.Error) as exc:
            raise ComputeError("CSV header is invalid") from exc
        columns = tuple(cell.strip() for cell in header)
        _columns(columns)
        raw_rows: list[tuple[str, ...]] = []
        try:
            for index, row in enumerate(reader, start=1):
                if index > max_rows:
                    raise ComputeError("CSV row limit exceeded")
                if len(row) != len(columns):
                    raise ComputeError("CSV row width does not match header")
                raw_rows.append(tuple(row))
        except csv.Error as exc:
            raise ComputeError("CSV payload is malformed") from exc
        types = tuple(
            _infer_type(tuple(row[index] for row in raw_rows)) for index in range(len(columns))
        )
        rows = tuple(
            tuple(_convert(value, types[index]) for index, value in enumerate(row))
            for row in raw_rows
        )
        value = Table(columns, types, rows, _table_digest(columns, types, rows))
        return _artifact(
            "load_csv",
            value,
            _digest(payload),
            {"delimiter": delimiter, "max_rows": max_rows},
        )

    def inspect_schema(self, table: Table) -> ComputeArtifact:
        value = {
            "row_count": table.row_count,
            "column_count": len(table.columns),
            "columns": [
                {
                    "name": name,
                    "type": kind,
                    "nullable": any(row[index] is None for row in table.rows),
                }
                for index, (name, kind) in enumerate(zip(table.columns, table.types, strict=True))
            ],
        }
        return _artifact("inspect_schema", value, table.digest, {})

    def summarize(self, table: Table, columns: Sequence[str] | None = None) -> ComputeArtifact:
        selected = tuple(columns) if columns is not None else table.columns
        if not selected or len(set(selected)) != len(selected):
            raise ComputeError("summary columns are invalid")
        indexes = [_index(table, name) for name in selected]
        summaries: dict[str, Any] = {}
        for name, index in zip(selected, indexes, strict=True):
            values = [row[index] for row in table.rows if row[index] is not None]
            item: dict[str, Any] = {
                "count": len(values),
                "null_count": table.row_count - len(values),
                "distinct_count": len({_canonical(value) for value in values}),
            }
            if table.types[index] in {"integer", "number"} and values:
                numbers = [
                    float(value)
                    for value in values
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                ]
                item.update(
                    min=min(numbers),
                    max=max(numbers),
                    mean=math.fsum(numbers) / len(numbers),
                    median=float(median(numbers)),
                )
            summaries[name] = item
        return _artifact("summarize", summaries, table.digest, {"columns": list(selected)})

    def select(self, table: Table, columns: Sequence[str]) -> ComputeArtifact:
        selected = tuple(columns)
        if not selected or len(set(selected)) != len(selected):
            raise ComputeError("selected columns are invalid")
        indexes = tuple(_index(table, name) for name in selected)
        rows = tuple(tuple(row[index] for index in indexes) for row in table.rows)
        types = tuple(table.types[index] for index in indexes)
        value = Table(selected, types, rows, _table_digest(selected, types, rows))
        return _artifact("select", value, table.digest, {"columns": list(selected)})

    def sort(self, table: Table, column: str, *, descending: bool = False) -> ComputeArtifact:
        index = _index(table, column)
        if not isinstance(descending, bool):
            raise ComputeError("descending must be boolean")
        present = [row for row in table.rows if row[index] is not None]
        missing = [row for row in table.rows if row[index] is None]
        rows = tuple(
            sorted(present, key=lambda row: _sort_key(row[index]), reverse=descending) + missing
        )
        value = Table(
            table.columns,
            table.types,
            rows,
            _table_digest(table.columns, table.types, rows),
        )
        return _artifact("sort", value, table.digest, {"column": column, "descending": descending})

    def chart_inputs(self, table: Table, *, kind: str, x: str, y: str) -> ComputeArtifact:
        if kind not in {"bar", "line", "point"}:
            raise ComputeError("chart kind is unsupported")
        x_index, y_index = _index(table, x), _index(table, y)
        if table.types[y_index] not in {"integer", "number"}:
            raise ComputeError("chart y column must be numeric")
        value = {
            "kind": kind,
            "x": x,
            "y": y,
            "data": [{x: row[x_index], y: row[y_index]} for row in table.rows],
        }
        return _artifact("chart_inputs", value, table.digest, {"kind": kind, "x": x, "y": y})


def _columns(columns: tuple[str, ...]) -> None:
    if not columns or len(columns) > MAX_COLUMNS or len(set(columns)) != len(columns):
        raise ComputeError("CSV columns are invalid")
    if any(not column or len(column) > 256 for column in columns):
        raise ComputeError("CSV column name is invalid")


def _infer_type(values: tuple[str, ...]) -> str:
    present = tuple(value.strip() for value in values if value.strip())
    if not present:
        return "string"
    if all(value.lower() in {"true", "false"} for value in present):
        return "boolean"
    try:
        for value in present:
            int(value)
        return "integer"
    except ValueError:
        pass
    try:
        numbers = [float(value) for value in present]
        if all(math.isfinite(value) for value in numbers):
            return "number"
    except ValueError:
        pass
    return "string"


def _convert(value: str, kind: str) -> Scalar:
    stripped = value.strip()
    if not stripped:
        return None
    if kind == "boolean":
        return stripped.lower() == "true"
    if kind == "integer":
        return int(stripped)
    if kind == "number":
        return float(stripped)
    return value


def _index(table: Table, column: str) -> int:
    try:
        return table.columns.index(column)
    except ValueError as exc:
        raise ComputeError("column does not exist") from exc


def _artifact(
    operation: str,
    value: Any,
    input_digest: str,
    parameters: Mapping[str, Any],
) -> ComputeArtifact:
    output_digest = _digest(_canonical(_json_value(value)).encode())
    return ComputeArtifact(
        operation,
        value if isinstance(value, Table) else _freeze(value),
        Provenance(ENGINE, ENGINE_VERSION, input_digest, parameters, None, output_digest),
    )


def _table_digest(
    columns: tuple[str, ...],
    types: tuple[str, ...],
    rows: tuple[tuple[Scalar, ...], ...],
) -> str:
    return _digest(_canonical({"columns": columns, "types": types, "rows": rows}).encode())


def _json_value(value: Any) -> Any:
    if isinstance(value, Table):
        return {
            "columns": value.columns,
            "types": value.types,
            "rows": value.rows,
            "digest": value.digest,
        }
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sort_key(value: Scalar) -> tuple[int, float, str]:
    if isinstance(value, bool):
        return (1, float(value), "")
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    if isinstance(value, str):
        return (2, 0.0, value)
    raise ComputeError("sort value is invalid")


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
