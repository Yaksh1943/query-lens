"""
Prompt templates for the Text-to-SQL pipeline.

Kept separate from app/llm/provider.py and app/core/sql_generation.py so
wording can be iterated on without touching orchestration or API logic.
"""


def build_sql_prompt(question: str, schema_text: str) -> str:
    """
    Builds the prompt that asks the LLM to turn a natural-language
    question into a single PostgreSQL SELECT statement.
    """
    return f"""You are a PostgreSQL expert. Given a database schema and a question, \
write a single SQL query that answers the question.

Database schema:
{schema_text}

Rules:
- Output ONLY the raw SQL query. No markdown code fences, no explanation, no comments.
- Use only the exact table and column names given in the schema above.
- Write a single SELECT statement only. Never write INSERT, UPDATE, DELETE, DROP, or ALTER.
- If the question requires aggregation (counts, sums, averages), use appropriate GROUP BY / aggregate functions.
- If a natural row limit isn't implied by the question, do not add one — LIMIT will be applied automatically if needed.

Question: {question}

SQL query:"""


def build_answer_prompt(question: str, sql: str, rows: list[dict]) -> str:
    """
    Builds the prompt that asks the LLM to turn a question + the SQL
    that was run + the resulting rows into a plain-English answer.
    """
    rows_preview = rows[:20]  # cap what we send back to the model
    truncated_note = f"\n(showing first 20 of {len(rows)} rows)" if len(rows) > 20 else ""

    return f"""You answered a user's question by running a SQL query against a database. \
Given the question, the SQL, and the resulting rows, write a short, clear, natural-language answer.

Question: {question}

SQL that was run:
{sql}

Result rows:
{rows_preview}{truncated_note}

Rules:
- Answer in plain English, directly addressing the question.
- Be concise — 1-3 sentences unless the data genuinely requires a list.
- Do not mention SQL, queries, or databases in your answer — just answer the question naturally.
- If the result rows are empty, say clearly that no matching data was found.

Answer:"""