from getpass import getpass

import psycopg


connection_string = getpass(
    "Paste your Neon connection string, then press Enter: "
).strip()

if not connection_string.startswith(("postgresql://", "postgres://")):
    raise SystemExit(
        "Copy only the connection URL, starting with postgresql://. "
        "Do not include a psql command or quotation marks."
    )

try:
    with psycopg.connect(
        connection_string,
        connect_timeout=20,
        sslmode="require",
        prepare_threshold=None,
    ) as connection:
        connection.read_only = True

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Unexpected query result.")

            cursor.execute("SHOW transaction_read_only")
            read_only = cursor.fetchone()[0]

        print("Neon connection: PASS")
        print("Encrypted connection:", bool(connection.pgconn.ssl_in_use))
        print("Read-only transaction:", read_only)

except psycopg.Error as error:
    # Avoid printing connection details or credentials.
    raise SystemExit(
        f"Connection failed: {type(error).__name__}. "
        "Check the copied URL and your internet connection."
    ) from None

print("Finished. No tables or records were created or changed.")