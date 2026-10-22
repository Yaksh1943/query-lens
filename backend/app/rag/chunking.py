"""
Structural chunking for SQL database schemas and few-shot examples.

Chunks are semantic entities (Tables, Columns, Relationships, Golden Queries),
preserving schema relational graph information rather than breaking across arbitrary token boundaries.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaTableChunk:
    table_name: str
    columns: list[dict[str, Any]]
    primary_keys: list[str]
    foreign_keys: list[dict[str, str]]
    description: str = ""

    def to_text(self) -> str:
        """Serializes the table chunk into semantic descriptive context for dense embedding."""
        col_strs = []
        for c in self.columns:
            name = c.get("name", "")
            data_type = str(c.get("type", "UNKNOWN"))
            is_pk = "PK" if name in self.primary_keys else ""
            fk_target = ""
            for fk in self.foreign_keys:
                if fk.get("constrained_columns", [None])[0] == name:
                    fk_target = f"FK -> {fk.get('referred_table')}.{fk.get('referred_columns', [''])[0]}"
                    break
            attrs = [a for a in [is_pk, fk_target] if a]
            attr_str = f" ({', '.join(attrs)})" if attrs else ""
            col_strs.append(f"{name} {data_type}{attr_str}")

        fk_lines = []
        for fk in self.foreign_keys:
            r_tbl = fk.get("referred_table")
            c_cols = ", ".join(fk.get("constrained_columns", []))
            r_cols = ", ".join(fk.get("referred_columns", []))
            fk_lines.append(f"Foreign Key: {self.table_name}({c_cols}) references {r_tbl}({r_cols})")

        fk_text = "\nRelationships:\n" + "\n".join(fk_lines) if fk_lines else ""
        desc_text = f"\nDescription: {self.description}" if self.description else ""

        return (
            f"Table Name: {self.table_name}\n"
            f"Columns: {', '.join(col_strs)}"
            f"{fk_text}"
            f"{desc_text}"
        )


@dataclass
class GoldenQueryChunk:
    question: str
    sql: str
    explanation: str = ""
    tables_used: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        return (
            f"Question: {self.question}\n"
            f"Explanation: {self.explanation}\n"
            f"SQL: {self.sql}"
        )
