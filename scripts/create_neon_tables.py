from getpass import getpass
from pathlib import Path
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))

from app import create_app
from app.extensions import db
from flask_migrate import upgrade


connection_string = getpass(
    "Paste the connection string for your empty Neon database: "
).strip()

try:
    url = make_url(connection_string)

    if url.drivername not in ("postgresql", "postgres"):
        raise ValueError("Expected a PostgreSQL URL.")

    if not url.host or not url.host.endswith(".neon.tech"):
        raise ValueError("Expected a Neon database address.")

    url = url.set(drivername="postgresql+psycopg")

except ValueError:
    raise SystemExit("Invalid Neon connection URL.") from None


app = create_app({
    "SQLALCHEMY_DATABASE_URI": url,
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "connect_args": {
            "sslmode": "require",
            "connect_timeout": 20,
            "prepare_threshold": None,
        },
        "pool_pre_ping": True,
        "hide_parameters": True,
    },
})

with app.app_context():
    try:
        inspector = inspect(db.engine)
        existing = (
            inspector.get_table_names(schema="public")
            + inspector.get_view_names(schema="public")
        )

        if existing:
            raise SystemExit(
                "Stopped: this database already contains tables or views. "
                "Nothing was changed by this script."
            )

        upgrade(directory=str(project / "migrations"))

        tables = set(
            inspect(db.engine).get_table_names(schema="public")
        )
        expected = set(db.metadata.tables) | {"alembic_version"}

        if tables != expected:
            raise RuntimeError("Unexpected tables after migration.")

        revision = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

        print("Neon schema creation: PASS")
        print("Application tables:", len(db.metadata.tables))
        print("Migration revision:", revision)
        print("No accounts, workers, or tasks have been imported yet.")

    except Exception as error:
        db.session.rollback()
        raise SystemExit(
            f"Schema setup stopped: {type(error).__name__}. "
            "Send only this error type for investigation."
        ) from None

    finally:
        db.session.remove()
        db.engine.dispose()