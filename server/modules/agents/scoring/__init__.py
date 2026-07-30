"""Code-side scoring engine for SME criteria.

The LLM only enumerates units and makes per-item judgments; everything in this
package turns those measurements into a 1-4 band deterministically, so the same
measurements always yield the same score. See openspec/specs/sme-engine-scoring/spec.md.
"""
