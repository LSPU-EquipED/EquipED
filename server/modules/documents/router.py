"""Scaffold router for the documents module."""

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])


__all__ = ["router"]
