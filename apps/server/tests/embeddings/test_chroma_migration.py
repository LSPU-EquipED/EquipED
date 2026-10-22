from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "migrate_chroma_cloud.py"
SPEC = importlib.util.spec_from_file_location("migrate_chroma_cloud", SCRIPT)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class FakeCollection:
    def __init__(self, name, records, metadata=None, reverse=False):
        self.name = name
        self.records = list(records)
        self.metadata = metadata
        self.configuration = {
            "hnsw": {"space": (metadata or {}).get("hnsw:space", "l2")}
        }
        self.batch_calls = []
        self.reverse = reverse

    def get(self, *, limit, offset, include):
        self.batch_calls.append((limit, offset))
        subset = self.records[offset : offset + limit]
        if self.reverse:
            subset = list(reversed(subset))
        return {
            "ids": [record["id"] for record in subset],
            "documents": [record["document"] for record in subset],
            "metadatas": [record["metadata"] for record in subset],
            "embeddings": [record["embedding"] for record in subset],
        }

    def count(self):
        return len(self.records)

    def add(self, *, ids, embeddings, documents=None, metadatas=None):
        documents = documents or [None] * len(ids)
        metadatas = metadatas or [None] * len(ids)
        self.records.extend(
            {"id": i, "document": d, "metadata": m, "embedding": e}
            for i, d, m, e in zip(ids, documents, metadatas, embeddings, strict=True)
        )


class FakeClient:
    def __init__(self, collections=()):
        self.collections = {collection.name: collection for collection in collections}
        self.created = []

    def list_collections(self):
        return list(self.collections.values())

    def get_collection(self, name, *, embedding_function=None):
        assert embedding_function is None
        return self.collections[name]

    def create_collection(self, *, name, metadata, embedding_function, configuration):
        assert embedding_function is None
        collection = FakeCollection(name, [], metadata)
        collection.configuration = configuration or {}
        self.collections[name] = collection
        self.created.append((name, metadata, configuration))
        return collection


@pytest.fixture
def sample_source():
    return FakeClient(
        [
            FakeCollection(
                "refs",
                [
                    {
                        "id": "a",
                        "document": "alpha",
                        "metadata": {"kind": "ref"},
                        "embedding": [0.1, 0.2],
                    },
                    {
                        "id": "b",
                        "document": None,
                        "metadata": None,
                        "embedding": [0.3, 0.4],
                    },
                    {
                        "id": "c",
                        "document": "gamma",
                        "metadata": {"page": 0},
                        "embedding": [0.5, 0.6],
                    },
                ],
                {"owner": "private", "hnsw:space": "cosine"},
            ),
        ]
    )


def test_migration_batches_records_and_preserves_payload_and_metric(sample_source):
    destination = FakeClient()
    result = migration.migrate_chroma(
        sample_source, destination, apply=True, batch_size=2
    )
    copied = destination.collections["refs"]
    assert copied.records == sample_source.collections["refs"].records
    assert copied.metadata == {"owner": "private", "hnsw:space": "cosine"}
    assert destination.created[0][2] == {"spann": {"space": "cosine"}}
    assert [offset for _, offset in copied.batch_calls] == [0, 2, 3]
    assert result["collections"][0]["count"] == 3


def test_exact_rerun_is_idempotent_and_float32_canonical(sample_source):
    destination = FakeClient()
    migration.migrate_chroma(sample_source, destination, apply=True, batch_size=2)
    # Python floats differ, but round to the same Chroma float32 values.
    collection = destination.collections["refs"]
    collection.records[0]["embedding"] = [0.100000001, 0.200000001]
    migration.migrate_chroma(sample_source, destination, apply=True, batch_size=2)
    assert len(collection.records) == 3


def test_divergent_destination_is_refused_without_overwrite(sample_source):
    dest = FakeCollection(
        "refs",
        [
            {
                "id": "a",
                "document": "changed",
                "metadata": {"kind": "ref"},
                "embedding": [0.1, 0.2],
            },
        ],
        sample_source.collections["refs"].metadata,
    )
    dest.configuration = {"hnsw": {"space": "cosine"}}
    destination = FakeClient([dest])
    with pytest.raises(migration.MigrationError, match="destination_mismatch"):
        migration.migrate_chroma(sample_source, destination, apply=True)
    assert dest.records[0]["document"] == "changed"


def test_report_contains_only_counts_hashes_and_not_payload(sample_source):
    report = migration.migrate_chroma(sample_source, FakeClient())
    rendered = __import__("json").dumps(report)
    assert "alpha" not in rendered
    assert "private" not in rendered
    assert report["collections"][0]["source_sha256"]


def test_verification_detects_vector_difference(sample_source):
    source = sample_source.collections["refs"]
    dest = FakeCollection(
        "refs",
        [
            {**source.records[0], "embedding": [9, 9]},
            *source.records[1:],
        ],
        source.metadata,
    )
    dest.configuration = {"hnsw": {"space": "cosine"}}
    destination = FakeClient([dest])
    with pytest.raises(migration.MigrationError, match="destination_mismatch"):
        migration.migrate_chroma(sample_source, destination, verify_only=True)


def test_collection_order_does_not_affect_verification(sample_source):
    source_collection = sample_source.collections["refs"]
    source_collection.reverse = True
    destination_collection = FakeCollection(
        "refs",
        list(reversed(source_collection.records)),
        source_collection.metadata,
    )
    destination_collection.configuration = {"hnsw": {"space": "cosine"}}
    report = migration.migrate_chroma(
        sample_source, FakeClient([destination_collection]), verify_only=True
    )
    assert report["collections"][0]["status"] == "verified"


def test_apply_resumes_identical_partial_copy(sample_source):
    source_collection = sample_source.collections["refs"]
    destination_collection = FakeCollection(
        "refs", [source_collection.records[0]], source_collection.metadata
    )
    destination_collection.configuration = {"hnsw": {"space": "cosine"}}
    destination = FakeClient([destination_collection])
    migration.migrate_chroma(sample_source, destination, apply=True, batch_size=1)
    assert len(destination_collection.records) == 3
    assert sorted(record["id"] for record in destination_collection.records) == [
        "a",
        "b",
        "c",
    ]


def test_verify_only_rejects_missing_collection(sample_source):
    with pytest.raises(migration.MigrationError, match="verification_failed"):
        migration.migrate_chroma(sample_source, FakeClient(), verify_only=True)


def test_metric_reads_hnsw_when_spann_is_explicitly_none():
    collection = FakeCollection("refs", [], metadata=None)
    collection.configuration = {"hnsw": {"space": "l2"}, "spann": None}
    source = FakeClient([collection])
    report = migration.migrate_chroma(source, FakeClient())
    assert report["collections"][0]["distance_metric"] == "l2"


def test_metric_conflict_between_metadata_and_configuration_fails():
    collection = FakeCollection("refs", [], metadata={"hnsw:space": "cosine"})
    collection.configuration = {"hnsw": {"space": "l2"}, "spann": None}
    with pytest.raises(migration.MigrationError, match="distance_metric_conflict"):
        migration.migrate_chroma(FakeClient([collection]), FakeClient())
