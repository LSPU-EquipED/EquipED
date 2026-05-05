"""Scaffold router for the evaluations module."""

from fastapi import APIRouter

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


__all__ = ["router"]
