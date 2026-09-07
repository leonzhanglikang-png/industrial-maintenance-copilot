from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.app.api.dependencies import get_retriever
from backend.app.infrastructure.persistent_retriever import PersistentSearchIndex
from backend.app.ports.retrieval import SearchIndex
from backend.app.schemas.documents import (
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
)
from backend.app.services.document_ingestion import (
    MAX_UPLOAD_BYTES,
    ingest_document,
)

router = APIRouter(tags=["documents"])


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    retriever: Annotated[
        SearchIndex,
        Depends(get_retriever),
    ],
) -> DocumentUploadResponse:
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        result = await run_in_threadpool(
            ingest_document,
            file.filename or "",
            content,
            retriever,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    return DocumentUploadResponse(
        document_id=result.document.document_id,
        source=result.document.source,
        content_type=result.document.content_type,
        chunk_count=result.chunk_count,
        indexed_chunk_count=result.indexed_chunk_count,
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    retriever: Annotated[PersistentSearchIndex, Depends(get_retriever)],
) -> DocumentListResponse:
    return DocumentListResponse(
        documents=[DocumentSummary(**item) for item in retriever.list_documents()]
    )
