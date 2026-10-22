"""Copy stored Chroma records to Chroma Cloud without re-embedding them."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


class MigrationError(Exception):
    """A safe, category-only migration failure."""


def _metric(collection: Any) -> str | None:
    metadata = collection.metadata or {}
    legacy_metric = metadata.get("hnsw:space")
    try:
        config = collection.configuration
        configured_metric = (config.get("spann") or {}).get("space") or (
            config.get("hnsw") or {}
        ).get("space")
    except (AttributeError, TypeError):
        configured_metric = None
    if legacy_metric and configured_metric and legacy_metric != configured_metric:
        raise MigrationError("distance_metric_conflict")
    return configured_metric or legacy_metric


def _float32(value: Any) -> bytes:
    number = float(value)
    if not math.isfinite(number):
        raise MigrationError("invalid_vector")
    return struct.pack("!f", number)


def _normalize(batch: dict[str, Any]) -> dict[str, list[Any]]:
    ids = list(batch.get("ids") or [])
    docs = batch.get("documents")
    metas = batch.get("metadatas")
    embeddings = batch.get("embeddings")
    return {
        "ids": ids,
        "documents": list(docs) if docs is not None else [None] * len(ids),
        "metadatas": list(metas) if metas is not None else [None] * len(ids),
        "embeddings": list(embeddings) if embeddings is not None else [None] * len(ids),
    }


def _records(collection: Any, batch_size: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = _normalize(
            collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents", "metadatas", "embeddings"],
            )
        )
        if not batch["ids"]:
            break
        result.extend(_as_records(batch))
        offset += len(batch["ids"])
    for record in result:
        if record["embedding"] is None:
            raise MigrationError("missing_vector")
        for component in record["embedding"]:
            _float32(component)
    result.sort(key=lambda record: record["id"])
    return result


def _digest(records: list[dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for record in records:
        hasher.update(
            json.dumps(record["id"], sort_keys=True, ensure_ascii=False).encode()
        )
        for field in ("document", "metadata"):
            hasher.update(
                json.dumps(record[field], sort_keys=True, ensure_ascii=False).encode()
            )
        vector = record["embedding"]
        if vector is None:
            hasher.update(b"null")
        else:
            for component in vector:
                hasher.update(_float32(component))
    return hasher.hexdigest()


def _as_records(batch: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize(batch)
    return [
        {
            "id": normalized["ids"][index],
            "document": normalized["documents"][index],
            "metadata": normalized["metadatas"][index],
            "embedding": normalized["embeddings"][index],
        }
        for index in range(len(normalized["ids"]))
    ]


def _same(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["id"] == right["id"]
        and left["document"] == right["document"]
        and left["metadata"] == right["metadata"]
        and (
            left["embedding"] is None
            and right["embedding"] is None
            or left["embedding"] is not None
            and right["embedding"] is not None
            and len(left["embedding"]) == len(right["embedding"])
            and all(
                _float32(a) == _float32(b)
                for a, b in zip(left["embedding"], right["embedding"], strict=True)
            )
        )
    )


def _add_records(collection: Any, records: list[dict[str, Any]]) -> None:
    """Submit homogeneous optional-field groups, omitting absent Chroma fields."""
    groups: dict[tuple[bool, bool], list[dict[str, Any]]] = {}
    for record in records:
        key = (record["document"] is not None, record["metadata"] is not None)
        groups.setdefault(key, []).append(record)
    for (has_documents, has_metadata), group in groups.items():
        values: dict[str, Any] = {
            "ids": [record["id"] for record in group],
            "embeddings": [record["embedding"] for record in group],
        }
        if has_documents:
            values["documents"] = [record["document"] for record in group]
        if has_metadata:
            values["metadatas"] = [record["metadata"] for record in group]
        collection.add(**values)


def migrate_chroma(
    source_client: Any,
    destination_client: Any,
    *,
    apply: bool = False,
    verify_only: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Inventory, copy, or verify all source collections using supplied clients."""
    if batch_size < 1:
        raise MigrationError("invalid_batch_size")
    try:
        source_collections = source_client.list_collections()
        summaries = []
        for source in source_collections:
            collection_name = source if isinstance(source, str) else source.name
            source_collection = source_client.get_collection(
                collection_name, embedding_function=None
            )
            source_count = source_collection.count()
            source_records = _records(source_collection, batch_size)
            if (
                len(source_records) != source_count
                or source_collection.count() != source_count
            ):
                raise MigrationError("source_changed_during_read")
            name = source_collection.name
            metric = _metric(source_collection) or "l2"
            if metric not in {"l2", "cosine", "ip"}:
                raise MigrationError("unsupported_distance_metric")
            destination_names = destination_client.list_collections()
            names = {
                item if isinstance(item, str) else item.name
                for item in destination_names
            }
            destination_collection = None
            if name in names:
                destination_collection = destination_client.get_collection(
                    name, embedding_function=None
                )
                destination_records = _records(destination_collection, batch_size)
                if destination_collection.metadata != source_collection.metadata:
                    raise MigrationError("destination_metadata_mismatch")
                if _metric(destination_collection) != metric:
                    raise MigrationError("destination_metric_mismatch")
                source_by_id = {record["id"]: record for record in source_records}
                for record in destination_records:
                    expected = source_by_id.get(record["id"])
                    if expected is None or not _same(expected, record):
                        raise MigrationError("destination_mismatch")
                if (not apply or verify_only) and len(destination_records) != len(
                    source_records
                ):
                    raise MigrationError("destination_mismatch")
            else:
                destination_records = []
            if verify_only:
                if destination_collection is None:
                    raise MigrationError("verification_failed")
                if len(source_records) != len(destination_records) or any(
                    not _same(a, b)
                    for a, b in zip(source_records, destination_records, strict=True)
                ):
                    raise MigrationError("verification_failed")
            elif apply and destination_collection is None:
                destination_collection = destination_client.create_collection(
                    name=name,
                    metadata=source_collection.metadata,
                    embedding_function=None,
                    configuration={"spann": {"space": metric}} if metric else None,
                )
            if destination_collection is not None:
                if destination_collection.metadata != source_collection.metadata:
                    raise MigrationError("destination_metadata_mismatch")
                if _metric(destination_collection) != metric:
                    raise MigrationError("destination_metric_mismatch")
            if apply and destination_collection is not None and not verify_only:
                existing_ids = {record["id"] for record in destination_records}
                missing_records = [
                    record
                    for record in source_records
                    if record["id"] not in existing_ids
                ]
                for start in range(0, len(missing_records), batch_size):
                    records = missing_records[start : start + batch_size]
                    _add_records(destination_collection, records)
                destination_records = _records(destination_collection, batch_size)
            if apply and not verify_only:
                if len(source_records) != len(destination_records) or any(
                    not _same(a, b)
                    for a, b in zip(source_records, destination_records, strict=True)
                ):
                    raise MigrationError("verification_failed")
            summaries.append(
                {
                    "collection": name,
                    "count": len(source_records),
                    "source_sha256": _digest(source_records),
                    "destination_count": len(destination_records),
                    "destination_sha256": _digest(destination_records),
                    "distance_metric": metric,
                    "status": "verified" if verify_only or apply else "inventory",
                }
            )
        return {"collections": summaries, "collection_count": len(summaries)}
    except MigrationError:
        raise
    except Exception:
        # Vendor exceptions can contain URLs, tenant names, or credentials.
        raise MigrationError("chroma_operation_failed") from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_path", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="write source records to Chroma Cloud"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="compare source and cloud without writes",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--report", type=Path, help="write a safe JSON count and hash manifest"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and args.verify_only:
        print("error: invalid_mode", file=sys.stderr)
        return 2
    try:
        if not (args.source_path / "chroma.sqlite3").is_file():
            raise MigrationError("source_database_missing")
        from server.core.config import get_settings

        settings = get_settings()
        if (
            settings.chroma_host
            and settings.chroma_host.strip().lower() != "api.trychroma.com"
        ):
            raise MigrationError("cloud_destination_required")
        if not all(
            (settings.chroma_api_key, settings.chroma_tenant, settings.chroma_database)
        ):
            raise MigrationError("cloud_credentials_required")
        import chromadb

        source = chromadb.PersistentClient(path=str(args.source_path))
        from server.core.chroma import get_chroma_client

        destination = get_chroma_client()
        report = migrate_chroma(
            source,
            destination,
            apply=args.apply,
            verify_only=args.verify_only,
            batch_size=args.batch_size,
        )
        rendered = json.dumps(report, sort_keys=True)
        if args.report:
            args.report.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("error: chroma_setup_failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
