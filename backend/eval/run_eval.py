"""
Evaluation harness for the Text-to-SQL pipeline.

Schema-agnostic by design: it never hardcodes Chinook or any other
dataset. It calls the same pipeline components the API uses
(generate_sql, validate_sql, execute_query, detect_ambiguity), which
already read the target database from backend/.env via
app.db.session. To evaluate against a different dataset, point
ANALYTICS_DATABASE_URL at that database and write a new test-cases
file with questions for its schema — this script does not change.

Two modes are run per test case:
- ON:  ambiguity check runs first (matches real API behavior)
- OFF: ambiguity check is bypassed, SQL is always generated

For unambiguous cases, "pass" = generated SQL's result rows match
the expected SQL's result rows (execution accuracy).
For ambiguous cases, there is no single correct SQL by design —
"pass" (in ON mode) = the ambiguity check correctly flagged it.
OFF mode on ambiguous cases has no pass/fail; it just shows what the
model would have generated blind, for comparison.

Token tracking: every LLM call made in each mode is summed, so the
report can show the real token cost of the ambiguity-check safety
net (ON) versus generating blind (OFF).

Two outputs are written per run:
- report.md   — human-readable, for the repo/README
- report.json — structured, consumed live by GET /api/insights and
  rendered on the frontend's Insights page. Includes a generated_at
  timestamp so staleness is always visible, never silent.

Row comparison limitation, stated plainly: rows are compared as
value-multisets with column names and row order ignored (so an
aliased column like `total_spending` vs `total` doesn't cause a
false mismatch). This means two structurally different queries that
happen to reduce to the same values would count as a match. Fine for
this test set's aggregation-heavy questions; would need tightening
for a larger or more adversarial suite.

Pacing: rate limiting lives in app.llm.provider.GeminiProvider itself
(throttled to stay under the free-tier requests-per-minute cap), so
this script doesn't need its own delay between cases.
"""
import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.ambiguity import detect_ambiguity
from app.core.config import get_settings
from app.core.sql_generation import generate_sql
from app.core.sql_validation import validate_sql
from app.db.analytics import execute_query
from app.db.schema import get_schema_snapshot
from app.llm.provider import GeminiProvider, LLMResponse

DEFAULT_TEST_FILE = Path(__file__).parent / "test_cases.json"
DEFAULT_REPORT_MD = Path(__file__).parent / "report.md"
DEFAULT_REPORT_JSON = Path(__file__).parent / "report.json"


@dataclass
class CaseResult:
    case_id: str
    question: str
    case_type: str
    notes: str
    on_passed: bool | None = None
    off_passed: bool | None = None
    on_sql: str | None = None
    off_sql: str | None = None
    on_flagged_ambiguous: bool | None = None
    off_flagged_ambiguous: bool | None = None
    on_input_tokens: int = 0
    on_output_tokens: int = 0
    off_input_tokens: int = 0
    off_output_tokens: int = 0
    detail: str = ""


def _sum_tokens(responses: list[LLMResponse]) -> tuple[int, int]:
    return (
        sum(r.input_tokens for r in responses),
        sum(r.output_tokens for r in responses),
    )


def normalize_rows(rows: list[dict]) -> list[tuple]:
    """
    Value-only, order-independent normalization: strips column names
    and row order so differently-aliased-but-equivalent queries still
    compare equal. See module docstring for the stated limitation.
    """
    normalized = [tuple(sorted(str(v) for v in row.values())) for row in rows]
    return sorted(normalized)


def rows_match(expected_rows: list[dict], actual_rows: list[dict]) -> bool:
    return normalize_rows(expected_rows) == normalize_rows(actual_rows)


def run_generation_pipeline(
    question: str, schema: dict, provider: GeminiProvider
) -> tuple[str | None, list[dict] | None, str, LLMResponse]:
    """Generates, validates, and executes SQL for a question. Returns (sql, rows, detail, llm_response)."""
    generated = generate_sql(question, provider)

    validation = validate_sql(generated.sql, schema)
    if not validation.is_valid:
        return generated.sql, None, f"Validation failed: {'; '.join(validation.errors)}", generated.raw_response

    result = execute_query(validation.sql)
    if not result.success:
        return validation.sql, None, f"Execution failed: {result.error}", generated.raw_response

    return validation.sql, result.rows, "ok", generated.raw_response


def evaluate_case(case: dict, schema: dict, provider: GeminiProvider) -> CaseResult:
    result = CaseResult(
        case_id=case["id"],
        question=case["question"],
        case_type=case["type"],
        notes=case.get("notes", ""),
    )

    # --- ON mode: real API behavior, ambiguity check first ---
    ambiguity = detect_ambiguity(case["question"], provider)
    on_responses = [ambiguity.raw_response]
    result.on_flagged_ambiguous = ambiguity.is_ambiguous

    if case["type"] == "ambiguous":
        result.on_passed = ambiguity.is_ambiguous is True
    else:
        if ambiguity.is_ambiguous:
            result.on_passed = False
            result.detail += "ON: false positive - flagged unambiguous question as ambiguous. "
        else:
            sql, rows, detail, gen_response = run_generation_pipeline(case["question"], schema, provider)
            on_responses.append(gen_response)
            result.on_sql = sql
            if rows is None:
                result.on_passed = False
                result.detail += f"ON: {detail}. "
            else:
                expected = execute_query(case["expected_sql"])
                result.on_passed = expected.success and rows_match(expected.rows, rows)
                if not result.on_passed:
                    result.detail += "ON: execution accuracy mismatch. "

    result.on_input_tokens, result.on_output_tokens = _sum_tokens(on_responses)

    # --- OFF mode: ambiguity check bypassed, always generate ---
    sql, rows, detail, gen_response = run_generation_pipeline(case["question"], schema, provider)
    off_responses = [gen_response]
    result.off_sql = sql
    result.off_input_tokens, result.off_output_tokens = _sum_tokens(off_responses)

    if case["type"] == "ambiguous":
        # No expected SQL to compare against - descriptive only.
        result.off_passed = None
        result.detail += f"OFF (blind generation, no ground truth): {sql or detail}. "
    else:
        if rows is None:
            result.off_passed = False
            result.detail += f"OFF: {detail}. "
        else:
            expected = execute_query(case["expected_sql"])
            result.off_passed = expected.success and rows_match(expected.rows, rows)
            if not result.off_passed:
                result.detail += "OFF: execution accuracy mismatch. "

    return result


def build_summary(results: list[CaseResult]) -> dict:
    """Shared summary numbers used by both the Markdown and JSON reports."""
    unambiguous = [r for r in results if r.case_type == "unambiguous"]
    ambiguous = [r for r in results if r.case_type == "ambiguous"]

    on_acc = sum(1 for r in unambiguous if r.on_passed) / len(unambiguous) if unambiguous else 0
    off_acc = sum(1 for r in unambiguous if r.off_passed) / len(unambiguous) if unambiguous else 0
    on_catch = sum(1 for r in ambiguous if r.on_passed) / len(ambiguous) if ambiguous else 0

    total_on_tokens = sum(r.on_input_tokens + r.on_output_tokens for r in results)
    total_off_tokens = sum(r.off_input_tokens + r.off_output_tokens for r in results)
    avg_on_tokens = total_on_tokens / len(results) if results else 0
    avg_off_tokens = total_off_tokens / len(results) if results else 0
    token_overhead_pct = ((total_on_tokens - total_off_tokens) / total_off_tokens * 100) if total_off_tokens else 0

    return {
        "total_cases": len(results),
        "unambiguous_cases": len(unambiguous),
        "ambiguous_cases": len(ambiguous),
        "execution_accuracy_on": on_acc,
        "execution_accuracy_off": off_acc,
        "ambiguity_catch_rate": on_catch,
        "total_tokens_on": total_on_tokens,
        "total_tokens_off": total_off_tokens,
        "avg_tokens_on": avg_on_tokens,
        "avg_tokens_off": avg_off_tokens,
        "token_overhead_pct": token_overhead_pct,
    }


def build_report_md(results: list[CaseResult], summary: dict, elapsed_s: float) -> str:
    unambiguous = [r for r in results if r.case_type == "unambiguous"]
    ambiguous = [r for r in results if r.case_type == "ambiguous"]

    lines = [
        "# QueryLens Evaluation Report",
        "",
        f"Total cases: {summary['total_cases']} "
        f"({summary['unambiguous_cases']} unambiguous, {summary['ambiguous_cases']} ambiguous)",
        f"Run time: {elapsed_s:.1f}s",
        "",
        "## Accuracy Summary",
        "",
        f"- **Execution accuracy, ambiguity check ON:** {summary['execution_accuracy_on']:.0%}",
        f"- **Execution accuracy, ambiguity check OFF:** {summary['execution_accuracy_off']:.0%}",
        f"- **Ambiguity catch rate (ON only):** {summary['ambiguity_catch_rate']:.0%}",
        "",
        "The ambiguity check is expected to make no difference to accuracy on "
        "clearly-specified questions (ON and OFF should match), and to be the "
        "only thing that catches genuinely ambiguous questions (OFF has no "
        "mechanism to catch them - it always generates blindly).",
        "",
        "## Token Cost Summary",
        "",
        f"- **Total tokens, ambiguity check ON:** {summary['total_tokens_on']:,}",
        f"- **Total tokens, ambiguity check OFF:** {summary['total_tokens_off']:,}",
        f"- **Average tokens per question, ON:** {summary['avg_tokens_on']:,.0f}",
        f"- **Average tokens per question, OFF:** {summary['avg_tokens_off']:,.0f}",
        f"- **Overhead of the ambiguity check:** {summary['token_overhead_pct']:+.1f}%",
        "",
        "On unambiguous questions, ON mode costs one extra LLM call (the "
        "ambiguity check itself) with no accuracy benefit - pure overhead. "
        "On ambiguous questions, that same call is what prevents the system "
        "from confidently generating and executing SQL for a question it "
        "cannot answer correctly - OFF mode has no equivalent safeguard and "
        "will always attempt an answer, right or wrong.",
        "",
        "## Unambiguous cases (execution accuracy + token cost)",
        "",
        "| ID | Question | ON pass | OFF pass | ON tokens | OFF tokens | Notes |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in unambiguous:
        on_tok = r.on_input_tokens + r.on_output_tokens
        off_tok = r.off_input_tokens + r.off_output_tokens
        lines.append(
            f"| {r.case_id} | {r.question} | {'✅' if r.on_passed else '❌'} | "
            f"{'✅' if r.off_passed else '❌'} | {on_tok:,} | {off_tok:,} | {r.notes} |"
        )

    lines += [
        "",
        "## Ambiguous cases (should be flagged, not answered blindly)",
        "",
        "| ID | Question | Flagged (ON) | ON tokens | OFF tokens (blind generation) | Notes |",
        "|---|---|---|---|---|---|",
    ]

    for r in ambiguous:
        on_tok = r.on_input_tokens + r.on_output_tokens
        off_tok = r.off_input_tokens + r.off_output_tokens
        lines.append(
            f"| {r.case_id} | {r.question} | {'✅' if r.on_passed else '❌'} | "
            f"{on_tok:,} | {off_tok:,} | {r.notes} |"
        )

    lines += ["", "### What the model generates for ambiguous questions if the check is bypassed", ""]
    for r in ambiguous:
        lines.append(f"**{r.case_id}** - *{r.question}*")
        lines.append(f"```sql\n{r.off_sql or '(no SQL - generation or validation failed)'}\n```")
        lines.append("")

    lines += ["## Per-case detail (failures and notes)", ""]
    for r in results:
        if r.detail:
            lines.append(f"- **{r.case_id}**: {r.detail}")

    return "\n".join(lines)


def build_report_json(results: list[CaseResult], summary: dict, elapsed_s: float) -> dict:
    """
    Structured version of the same report, consumed live by
    GET /api/insights and rendered on the frontend's Insights page.
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_time_seconds": round(elapsed_s, 1),
        "summary": summary,
        "cases": [asdict(r) for r in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the QueryLens evaluation harness.")
    parser.add_argument("--test-file", type=Path, default=DEFAULT_TEST_FILE)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    args = parser.parse_args()

    settings = get_settings()
    provider = GeminiProvider(api_key=settings.gemini_api_key)
    schema = get_schema_snapshot()

    test_cases = json.loads(args.test_file.read_text())

    start = time.monotonic()

    results: list[CaseResult] = []
    for i, case in enumerate(test_cases):
        print(f"[{i + 1}/{len(test_cases)}] Evaluating: {case['question']}")
        results.append(evaluate_case(case, schema, provider))

    elapsed_s = time.monotonic() - start
    summary = build_summary(results)

    args.output_md.write_text(build_report_md(results, summary, elapsed_s), encoding="utf-8")
    args.output_json.write_text(
        json.dumps(build_report_json(results, summary, elapsed_s), indent=2),
        encoding="utf-8",
    )

    print(f"\nEvaluated {len(results)} cases in {elapsed_s:.1f}s")
    print(f"Reports written to {args.output_md} and {args.output_json}")


if __name__ == "__main__":
    main()