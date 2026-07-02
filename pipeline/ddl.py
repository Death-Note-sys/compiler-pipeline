import logging
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import List, Optional

from schemas.db import ColumnType, DBSchema, DBTable

logger = logging.getLogger(__name__)

# SQLite reserved words that cannot be used as bare table names.
RESERVED = {
    "order", "group", "index", "table", "select", "where",
    "from", "create", "drop", "user", "key", "check",
    "default", "values", "set", "by", "as", "on",
}


def _quote_name(name: str) -> str:
    """Wrap a name in double-quotes if it is a reserved SQLite keyword."""
    return f'"{name}"' if name.lower() in RESERVED else name

@dataclass
class DDLValidationResult:
    """Result of validating DDL against an in-memory SQLite database."""
    success: bool
    error: Optional[str]
    table_count: int


def _topological_sort_tables(db_schema: DBSchema) -> List[DBTable]:
    """
    Order tables so referenced tables are created before the tables that
    reference them. Fall back to original order if a cycle is detected.
    """
    adj = defaultdict(list)
    in_degree = {table.name: 0 for table in db_schema.tables}
    table_map = {table.name: table for table in db_schema.tables}
    
    for table in db_schema.tables:
        for col in table.columns:
            if col.col_type == ColumnType.foreign_key and col.foreign_key:
                parts = col.foreign_key.split('.')
                if parts:
                    target_table = parts[0]
                    # Don't consider self-references for topological sort, and ensure target exists
                    if target_table in table_map and target_table != table.name:
                        adj[target_table].append(table.name)
                        in_degree[table.name] += 1
                        
    q = deque([t for t, deg in in_degree.items() if deg == 0])
    ordered = []
    
    while q:
        curr = q.popleft()
        ordered.append(table_map[curr])
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                q.append(neighbor)
                
    if len(ordered) != len(db_schema.tables):
        logger.warning("Cycle detected in foreign keys, falling back to original table order.")
        return db_schema.tables
        
    return ordered


def _map_col_type(col_type: ColumnType) -> str:
    """Map DB ColumnType to standard SQL type for SQLite."""
    mapping = {
        ColumnType.string: "VARCHAR",
        ColumnType.text: "TEXT",
        ColumnType.integer: "INTEGER",
        ColumnType.float_: "REAL",
        ColumnType.boolean: "BOOLEAN",
        ColumnType.date: "DATE",
        ColumnType.datetime: "DATETIME",
        ColumnType.uuid: "UUID",
        ColumnType.json: "JSON",
        ColumnType.enum: "TEXT",
        ColumnType.foreign_key: "INTEGER"
    }
    return mapping.get(col_type, "TEXT")


def generate_ddl(db_schema: DBSchema) -> str:
    """
    Generate valid SQL CREATE TABLE statements for the given DBSchema.
    Tables are ordered by foreign key dependencies.
    """
    lines = [
        "-- SQLite stores UUID as TEXT. In production (PostgreSQL), use UUID PRIMARY KEY DEFAULT gen_random_uuid().",
        "PRAGMA foreign_keys = ON;",
        ""
    ]
    
    ordered_tables = _topological_sort_tables(db_schema)
    
    for table in ordered_tables:
        lines.append(f"CREATE TABLE {_quote_name(table.name)} (")
        col_defs = []
        fk_constraints = []
        
        for col in table.columns:
            sql_type = _map_col_type(col.col_type)
            constraints = []
            
            # PRIMARY KEY for 'id' UUID columns
            if col.name == "id" and col.col_type == ColumnType.uuid:
                constraints.append("PRIMARY KEY")
            elif not col.nullable:
                constraints.append("NOT NULL")
                
            col_def = f"    {col.name} {sql_type}"
            if constraints:
                col_def += " " + " ".join(constraints)
            col_defs.append(col_def)
            
            # FOREIGN KEY constraints
            if col.col_type == ColumnType.foreign_key and col.foreign_key:
                parts = col.foreign_key.split('.')
                if len(parts) == 2:
                    ref_table, ref_col = parts
                    fk_constraints.append(f"    FOREIGN KEY ({col.name}) REFERENCES {_quote_name(ref_table)} ({ref_col})")
                    
        # Combine column definitions and constraints
        all_defs = col_defs + fk_constraints
        lines.append(",\n".join(all_defs))
        lines.append(");\n")
        
    return "\n".join(lines)


def validate_ddl(ddl: str) -> DDLValidationResult:
    """
    Run the DDL against an in-memory SQLite database to prove it executes.
    Returns the result of the validation and the number of tables created.
    """
    try:
        conn = sqlite3.connect(":memory:")
        # Execute script will throw an exception on syntax error or constraint failure
        conn.executescript(ddl)
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        
        return DDLValidationResult(success=True, error=None, table_count=len(tables))
    except Exception as e:
        return DDLValidationResult(success=False, error=str(e), table_count=0)
