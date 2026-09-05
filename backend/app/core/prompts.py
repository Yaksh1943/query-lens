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

def build_ambiguity_prompt(question: str, schema_text: str) -> str:
    """
    Builds the prompt that asks the LLM to judge whether a question is
    answerable unambiguously against the schema, before any SQL is
    generated.
    """
    return f"""You are a PostgreSQL expert reviewing a question before writing SQL for it. \
Given a database schema and a question, decide whether the question is clear enough to \
answer with a single, unambiguous SQL query.

Database schema:
{schema_text}

A question is ambiguous if:
- It's missing information needed to answer it precisely (e.g. "top customers" without \
saying by what measure — spending, order count, etc.)
- A word or phrase in the question could reasonably map to more than one table or column \
in the schema, and the correct choice isn't clear from context.
- It implies a time range or filter that isn't specified (e.g. "recent" orders).

A question is NOT ambiguous just because it's simple, broad, or could return many rows \
(e.g. "list all customers" is fine — it doesn't need clarification).

Question: {question}

Respond with ONLY a raw JSON object, no markdown fences, no explanation outside the JSON, \
in exactly this shape:
{{"is_ambiguous": true or false, "clarification_question": "a single, specific question \
to ask the user, or null if not ambiguous", "reasoning": "one short sentence explaining \
your judgment"}}"""

def build_table_selection_prompt(question: str, table_list_text: str) -> str:
    """
    Builds the stage-1 prompt for two-stage schema retrieval: asks the
    LLM which tables (by name only, no column detail) are relevant to
    a question, before paying for full schema detail on just those
    tables. See app.core.schema_selection for when this stage is used.
    """
    return f"""You are a PostgreSQL expert helping to scope which tables are needed to answer a question, \
before writing any SQL. You will NOT write SQL yet — you are only selecting relevant tables.

Available tables (name and column count only):
{table_list_text}

Question: {question}

Rules:
- Select every table that would actually be needed to answer this question, including tables \
needed only for joins (e.g. a question about "customers by spending" needs both the customers \
table and whatever table records purchases/invoices, even though "invoice" isn't mentioned).
- Prefer including a table you're unsure about over leaving out one you'll actually need — \
missing a required table will make the question unanswerable, while an extra table is harmless.
- Use the exact table names as given above.

Respond with ONLY a raw JSON array of table names, no markdown fences, no explanation, in \
exactly this shape:
["table_one", "table_two"]"""

def build_combined_prompt(question: str, schema_text: str) -> str:
    """
    Single call that both checks ambiguity and generates SQL — replaces
    two separate calls that each sent the same schema. See
    app.core.combined_check for the orchestration.
    """
    return f"""You are a PostgreSQL expert. Given a database schema and a question, first decide whether \
the question is clear enough to answer with a single, unambiguous SQL query. Then either ask for \
clarification or write the SQL — not both.

Database schema:
{schema_text}

A question is ambiguous if:
- It's missing information needed to answer it precisely (e.g. "top customers" without saying by \
what measure — spending, order count, etc.)
- A word or phrase could reasonably map to more than one table or column, and the correct choice \
isn't clear from context.
- It implies a time range or filter that isn't specified (e.g. "recent" orders).

A question is NOT ambiguous just because it's simple, broad, or could return many rows.

Question: {question}

If the question is ambiguous, respond with ONLY this JSON shape (sql must be null):
{{"is_ambiguous": true, "clarification_question": "a single, specific question to ask the user", "sql": null, "reasoning": "one short sentence"}}

If the question is NOT ambiguous, write a single PostgreSQL SELECT statement that answers it \
(use only the exact table/column names given above; never write INSERT, UPDATE, DELETE, DROP, \
or ALTER; a single statement only), and respond with ONLY this JSON shape (clarification_question \
must be null):
{{"is_ambiguous": false, "clarification_question": null, "sql": "SELECT ...", "reasoning": "one short sentence"}}

Respond with ONLY the raw JSON object, no markdown fences, no explanation outside the JSON."""