import sqlite3

from fastapi_app.database import ensure_sqlite_schema_compatibility


def test_ensure_sqlite_schema_compatibility_adds_missing_columns(tmp_path):
    db_path = tmp_path / "test_schema.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE accounts_baseuser (id INTEGER PRIMARY KEY, email VARCHAR(254) NOT NULL, password VARCHAR(128) NOT NULL)"
    )
    conn.commit()
    conn.close()

    ensure_sqlite_schema_compatibility(f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    columns = [row[1] for row in conn.execute("PRAGMA table_info('accounts_baseuser')")]
    conn.close()

    assert "role" in columns
    assert "razorpay_customer_id" in columns
