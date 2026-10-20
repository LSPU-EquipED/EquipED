"""Helpers used only to validate provenance in saved ITSO assessments."""

from urllib.parse import urlencode

from equiped_harness.tools.contracts import Code, VerificationError

from ..tools.contracts import PublicReference


def brave_url(ref: PublicReference) -> str:
    """Rebuild the retired Brave request URL for saved-ledger fingerprints."""
    # Exact approved fields only, no arbitrary model query or description.
    fields = [ref.title or "", *ref.authors]
    if ref.doi:
        fields.append(ref.doi)
    if ref.year:
        fields.append(str(ref.year))
    query = " ".join(fields)
    if len(query) > 1200:
        raise VerificationError(Code.INVALID, ref.reference_hash)
    return "https://api.search.brave.com/res/v1/web/search?" + urlencode(
        {"q": query, "count": 3, "safesearch": "strict", "text_decorations": "false"}
    )
