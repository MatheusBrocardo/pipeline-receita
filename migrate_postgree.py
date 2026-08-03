import psycopg2
import cx_Oracle
import gc

cx_Oracle.init_oracle_client(lib_dir=r"C:\oracle\instantclient_21_3")

# ------------------------
# CONEXÃO POSTGRES
# ------------------------
pg_conn = psycopg2.connect(
    host="127.0.0.1",
    database="cnpj",
    user="postgres",
    password="postgres",
    port="5435"
)

# ------------------------
# CONEXÃO ORACLE
# ------------------------
dsn = cx_Oracle.makedsn(
    host="192.168.1.225",
    port=1521,
    service_name="ORBI"
)

oracle_conn = cx_Oracle.connect(
    user="ORBI",
    password="ADMIN4ORBI",
    dsn=dsn
)

try:
    # 🔹 cursor normal (pra coisas pequenas)
    pg_cursor_default = pg_conn.cursor()

    # 🔹 cursor server-side (STREAM de verdade)
    pg_cursor = pg_conn.cursor(name="cursor_processed_files")
    BATCH_SIZE = 10000  # ↓ reduzimos pra evitar picos de memória
    pg_cursor.itersize = BATCH_SIZE

    oracle_cursor = oracle_conn.cursor()
    oracle_cursor.arraysize = BATCH_SIZE

    # ⚠️ EVITA SELECT * (melhor controle de memória)
    pg_cursor.execute("""
        SELECT *
        FROM processed_files
    """)

    insert_sql = """
        INSERT INTO SG3_PROCESSED_FILES
        VALUES (:1,:2,:3)
    """

    total = 0
    commit_lote = 50000  # commit a cada 50k (bem melhor)

    while True:
        chunk = pg_cursor.fetchmany(BATCH_SIZE)

        if not chunk:
            break

        oracle_cursor.executemany(insert_sql, chunk)
        total += len(chunk)

        # 🔥 commit controlado
        if total % commit_lote < BATCH_SIZE:
            oracle_conn.commit()
            print(f"commit parcial: {total}")

        # 🔥 limpa memória
        del chunk
        gc.collect()

    oracle_conn.commit()

    print(f"🚀 Finalizado! Total inserido: {total}")

except Exception as e:
    print("❌ Erro:", e)
    oracle_conn.rollback()

finally:
    try:
        pg_cursor.close()
    except:
        pass

    pg_cursor_default.close()
    oracle_cursor.close()
    pg_conn.close()
    oracle_conn.close()