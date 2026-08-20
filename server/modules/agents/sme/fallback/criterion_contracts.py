"""Closed, non-coercing contracts for the per-criterion SME fallback lane."""

from __future__ import annotations

from typing import Any


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
TEXT = {"type": "string"}
BLOOM = {
    "type": "string",
    "enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"],
}
ASSESSMENT_TYPE = {
    "type": "string",
    "enum": [
        "objective_test",
        "written",
        "reflection",
        "performance_task",
        "project",
        "oral",
        "self_assessment",
    ],
}
MONITORING_TYPE = {
    "type": "string",
    "enum": ["checkpoint", "self_assessment", "reflection", "cumulative"],
}
FEEDBACK_TYPE = {
    "type": "string",
    "enum": [
        "answer_key",
        "rubric",
        "remediation_referral",
        "positive_reinforcement",
    ],
}

_EMPTYABLE_FIELDS: frozenset[str] = frozenset(
    {"evidence", "directions", "reason", "issue"}
)

RESPONSE_SCHEMAS: dict[str, dict[str, Any]] = {
    "A-01": _object(
        {
            "tasks": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "bloom_level": BLOOM,
                        "evidence": TEXT,
                    }
                )
            )
        }
    ),
    "A-02": _object(
        {
            "assessments": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "assessment_type": ASSESSMENT_TYPE,
                        "evidence": TEXT,
                    }
                )
            )
        }
    ),
    "A-03": _object(
        {
            "mechanisms": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "monitoring_type": MONITORING_TYPE,
                        "evidence": TEXT,
                    }
                )
            )
        }
    ),
    "A-04": _object(
        {
            "mechanisms": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "feedback_type": FEEDBACK_TYPE,
                        "evidence": TEXT,
                    }
                )
            )
        }
    ),
    "A-05": _object(
        {
            "objectives": _array(_object({"id": INTEGER, "text": TEXT})),
            "assessments": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "assessment_type": ASSESSMENT_TYPE,
                        "evidence": TEXT,
                    }
                )
            ),
            "alignment": _array(
                _object(
                    {
                        "objective_id": INTEGER,
                        "is_measured": BOOLEAN,
                        "assessment_ids": _array(INTEGER),
                        "evidence": TEXT,
                    }
                )
            ),
        }
    ),
    "OP-01": _object(
        {
            "topics": _array(_object({"id": INTEGER, "title": TEXT})),
            "transitions": _array(
                _object(
                    {
                        "from_id": INTEGER,
                        "to_id": INTEGER,
                        "is_coherent": BOOLEAN,
                        "reason": TEXT,
                    }
                )
            ),
        }
    ),
    "OP-02": _object(
        {
            "interactive_elements": _array(
                _object({"id": INTEGER, "text": TEXT, "evidence": TEXT})
            )
        }
    ),
    "OP-03": _object(
        {
            "tasks": _array(
                _object(
                    {
                        "id": INTEGER,
                        "text": TEXT,
                        "directions": TEXT,
                        "has_clear_directions": BOOLEAN,
                        "evidence": TEXT,
                    }
                )
            )
        }
    ),
    "OP-04": _object(
        {
            "sections": _array(
                _object(
                    {
                        "id": INTEGER,
                        "title": TEXT,
                        "is_clean": BOOLEAN,
                        "issue": TEXT,
                    }
                )
            )
        }
    ),
    "OP-05": _object(
        {
            "enhancement_activities": _array(
                _object({"id": INTEGER, "text": TEXT, "evidence": TEXT})
            )
        }
    ),
}


def validate(code: str, value: Any) -> dict[str, Any]:
    schema = RESPONSE_SCHEMAS[code]
    if isinstance(value, dict):
        schema_props = schema.get("properties", {})
        for key, items in value.items():
            if isinstance(items, list) and key in schema_props:
                item_schema = schema_props[key].get("items", {})
                item_props = item_schema.get("properties", {})
                for item in items:
                    if isinstance(item, dict):
                        for field in _EMPTYABLE_FIELDS:
                            if field in item_props and field not in item:
                                item[field] = ""
    _check(value, schema, "$")
    _check_unique_ids(code, value)
    if code == "A-05":
        objective_ids = {row["id"] for row in value["objectives"]}
        assessment_ids = {row["id"] for row in value["assessments"]}
        rows_by_objective: dict[int, dict[str, Any]] = {}
        for item in value["alignment"]:
            oid = item["objective_id"]
            if oid in objective_ids and oid not in rows_by_objective:
                rows_by_objective[oid] = item
        normalized_alignment: list[dict[str, Any]] = []
        for oid in sorted(objective_ids):
            row = rows_by_objective.get(oid)
            if row is None:
                row = {
                    "objective_id": oid,
                    "is_measured": False,
                    "assessment_ids": [],
                    "evidence": "",
                }
            refs: list[int] = []
            seen_refs: set[int] = set()
            for ref in row.get("assessment_ids", []):
                if ref in assessment_ids and ref not in seen_refs:
                    refs.append(ref)
                    seen_refs.add(ref)
            row["assessment_ids"] = refs
            if row.get("is_measured") and (
                not refs or not row.get("evidence", "").strip()
            ):
                row["is_measured"] = False
                row["evidence"] = ""
            normalized_alignment.append(row)
        value["alignment"] = normalized_alignment
    if code == "OP-01":
        topic_ids = {row["id"] for row in value["topics"]}
        if any(
            row["from_id"] not in topic_ids or row["to_id"] not in topic_ids
            for row in value["transitions"]
        ):
            raise ValueError("invalid transition reference")
    return value


def _check_unique_ids(code: str, value: dict[str, Any]) -> None:
    for key, rows in value.items():
        ids = [row["id"] for row in rows if isinstance(row, dict) and "id" in row]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{code}: duplicate ids in {key}")


def _check(value: Any, schema: dict[str, Any], path: str) -> None:
    schema_type = schema["type"]
    if schema_type == "object":
        if not isinstance(value, dict):
            raise TypeError(f"{path} must be object")
        if set(value) != set(schema["required"]):
            raise ValueError(f"{path} keys mismatch")
        for key, child in schema["properties"].items():
            _check(value[key], child, f"{path}.{key}")
    elif schema_type == "array":
        if not isinstance(value, list):
            raise TypeError(f"{path} must be array")
        for index, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{index}]")
    elif schema_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{path} must be integer")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise TypeError(f"{path} must be boolean")
    elif schema_type == "string":
        if not isinstance(value, str):
            raise TypeError(f"{path} must be string")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"{path} invalid enum")


__all__ = ["RESPONSE_SCHEMAS", "_EMPTYABLE_FIELDS", "validate"]
