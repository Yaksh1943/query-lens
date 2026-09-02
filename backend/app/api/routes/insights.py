"""
GET /api/insights — serves the structured eval report (report.json)
produced by eval/run_eval.py, so the frontend can render a live
"how well does this actually work" comparison instead of a static
Markdown file nobody browsing the portfolio would open.

If report.json doesn't exist yet (fresh clone, eval never run),
returns a clear available=False response rather than a 500 — this is
an expected, normal state, not a server error.
"""
import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

REPORT_JSON_PATH = Path(__file__).resolve().parents[3] / "eval" / "report.json"


class InsightsResponse(BaseModel):
    available: bool
    data: dict | None = None
    message: str | None = None


@router.get("/insights", response_model=InsightsResponse)
def get_insights() -> InsightsResponse:
    if not REPORT_JSON_PATH.exists():
        return InsightsResponse(
            available=False,
            message="No evaluation report found yet. Run `python -m eval.run_eval` to generate one.",
        )

    try:
        data = json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
        return InsightsResponse(available=True, data=data)
    except (json.JSONDecodeError, OSError) as e:
        return InsightsResponse(
            available=False,
            message=f"Evaluation report exists but could not be read: {e}",
        )