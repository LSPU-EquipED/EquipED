"""Quick smoke test for the embeddings retrieval path."""

from __future__ import annotations

import argparse
from typing import Any

from server.modules.embeddings.collections import COL_SLM
from server.modules.embeddings.retrieval import retrieve_context


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query a Chroma embedding collection")
    parser.add_argument("query", nargs="?", default="lesson objectives")
    parser.add_argument("--collection", default=COL_SLM)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--limit", type=int, default=3)
    return parser


def _format_result(index: int, item: Any) -> str:
    lines = [f"Result {index}", f"distance: {item.distance}"]
    if item.document_id is not None:
        lines.append(f"document_id: {item.document_id}")
    if item.source_type is not None:
        lines.append(f"source_type: {item.source_type}")
    if item.page_number is not None:
        lines.append(f"page_number: {item.page_number}")
    if item.token_count is not None:
        lines.append(f"token_count: {item.token_count}")
    lines.append(item.text)
    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()
    results = retrieve_context(
        query_text=args.query,
        collection_name=args.collection,
        n_results=args.limit,
        document_id_filter=args.document_id,
    )

    print(f"collection: {args.collection}")
    print(f"query: {args.query}")
    print(f"matches: {len(results)}")

    for index, item in enumerate(results, start=1):
        print(_format_result(index, item))
        print("---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
