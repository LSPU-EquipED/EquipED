"""Scaffold router for the feedback module."""

from fastapi import APIRouter

router = APIRouter(prefix="/feedback", tags=["feedback"])


__all__ = ["router"]
