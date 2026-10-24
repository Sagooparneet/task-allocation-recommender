from getpass import getpass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


connection_string = getpass(
    "Paste your Neon connection string: "
).strip()

engine = None

try:
    url = make_url(connection_string)

    if url.drivername not in ("postgresql", "postgres"):
        raise ValueError("Expected a PostgreSQL connection URL.")

    # Select the Psycopg 3 driver used by our application.
    url = url.set(drivername="postgresql+psycopg")

    engine = create_engine(
        url,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 20,
            "prepare_threshold": None,
        },
        pool_pre_ping=True,
        hide_parameters=True,
    )

    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))

            result = connection.execute(text("SELECT 1")).scalar_one()
            table_count = connection.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)).scalar_one()

            print("SQLAlchemy connection:", "PASS" if result == 1 else "FAIL")
            print("Existing public tables:", table_count)

except (SQLAlchemyError, ValueError):
    raise SystemExit(
        "Check failed. Verify the connection URL and network access. "
        "Connection details have been hidden."
    ) from None

finally:
    if engine is not None:
        engine.dispose()

print("Finished. No tables or records were changed.")