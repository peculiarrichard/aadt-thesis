"""Orchestrates the guideline ingestion pipeline: PDF -> chunks -> embeddings ->
graph nodes/edges, all written to the DB for one GuidelineDocument per call.

CLI usage: uv run python -m backend.ingestion.pipeline --file <pdf> --title <title>
--source <source> [--edition <edition>] [--no-embed]
"""

import argparse
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.db.enums import GraphNodeType, GraphRelationType
from backend.db.models import (
    GuidelineChunk,
    GuidelineDocument,
    GuidelineGraphEdge,
    GuidelineGraphNode,
)
from backend.ingestion.chunking import chunk_lines
from backend.ingestion.embeddings import embed_texts
from backend.ingestion.graph_extraction import extract_condition_relations
from backend.ingestion.pdf_extract import extract_lines

_LABEL_MAX_LEN = 500


def ingest_document(
    session: Session,
    pdf_path: Path,
    title: str,
    source: str,
    edition: str | None = None,
    embed: bool = True,
) -> GuidelineDocument:
    """Parse, chunk, (optionally) embed, and graph-extract a guideline PDF into the DB.

    Always creates a new GuidelineDocument row; does not deduplicate against a
    previously ingested document with the same title.
    """
    document = GuidelineDocument(title=title, source=source, edition=edition)
    session.add(document)
    session.flush()

    lines = extract_lines(pdf_path)
    chunk_texts = chunk_lines(lines)
    vectors = embed_texts(chunk_texts) if embed else [None] * len(chunk_texts)

    node_cache: dict[tuple[GraphNodeType, str], GuidelineGraphNode] = {}

    for chunk_text, vector in zip(chunk_texts, vectors, strict=True):
        chunk = GuidelineChunk(
            document_id=document.document_id, content=chunk_text, embedding=vector
        )
        session.add(chunk)
        session.flush()

        for relation in extract_condition_relations(chunk_text.split("\n")):
            condition_node = _get_or_create_node(
                session,
                node_cache,
                document.document_id,
                GraphNodeType.CONDITION,
                relation.condition,
            )
            for symptom in relation.symptoms:
                symptom_node = _get_or_create_node(
                    session, node_cache, document.document_id, GraphNodeType.SYMPTOM, symptom
                )
                session.add(
                    GuidelineGraphEdge(
                        source_node_id=condition_node.node_id,
                        target_node_id=symptom_node.node_id,
                        relation_type=GraphRelationType.PRESENTS_WITH,
                        chunk_id=chunk.chunk_id,
                    )
                )
            for recommendation in relation.recommendations:
                recommendation_node = _get_or_create_node(
                    session,
                    node_cache,
                    document.document_id,
                    GraphNodeType.RECOMMENDATION,
                    recommendation,
                )
                session.add(
                    GuidelineGraphEdge(
                        source_node_id=condition_node.node_id,
                        target_node_id=recommendation_node.node_id,
                        relation_type=GraphRelationType.RECOMMENDS,
                        chunk_id=chunk.chunk_id,
                    )
                )

    session.commit()
    return document


def _get_or_create_node(
    session: Session,
    cache: dict[tuple[GraphNodeType, str], GuidelineGraphNode],
    document_id: uuid.UUID,
    node_type: GraphNodeType,
    label: str,
) -> GuidelineGraphNode:
    label = label[:_LABEL_MAX_LEN]
    key = (node_type, label)
    if key in cache:
        return cache[key]
    node = GuidelineGraphNode(document_id=document_id, node_type=node_type, label=label)
    session.add(node)
    session.flush()
    cache[key] = node
    return node


def _main() -> None:
    from backend.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Ingest a guideline PDF into the DB.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--edition", default=None)
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="skip BGE-M3 embedding (chunks are written with embedding=NULL)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        document = ingest_document(
            session,
            args.file,
            title=args.title,
            source=args.source,
            edition=args.edition,
            embed=not args.no_embed,
        )
        print(f"Ingested document {document.document_id} ({args.title})")
    finally:
        session.close()


if __name__ == "__main__":
    _main()
