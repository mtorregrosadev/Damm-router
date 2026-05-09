import sqlite3
import re
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "src/hackaton.db"

EXCEL_FILES = {
    "Hackaton.xlsx": {
        "Detalle entrega":      "detalle_entrega",
        "Cabecera Transporte":  "cabecera_transporte",
        "Direcciones":          "direcciones",
        "ZONAS":                "zonas",
        "Materiales zubic":     "materiales_zubic",
    },
    "Horarios Entrega.XLSX": {
        "Sheet1": "horarios_entrega",
    },
}


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def normalize_column(name: str, seen: dict) -> str:
    """Convierte un nombre de columna a snake_case válido para SQL.
    Desambigua duplicados añadiendo _2, _3, …"""
    if name is None:
        name = "col"
    name = str(name).strip()
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)   # caracteres especiales → _
    name = re.sub(r"_+", "_", name).strip("_")    # underscores múltiples
    name = name.lower() or "col"

    # desambiguar duplicados
    base = name
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count > 1:
        name = f"{base}_{count}"

    return name


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas y limpia el DataFrame."""
    seen: dict = {}
    new_cols = [normalize_column(c, seen) for c in df.columns]
    df.columns = new_cols
    return df


def infer_create_table(df: pd.DataFrame, table_name: str) -> str:
    """Genera un CREATE TABLE IF NOT EXISTS a partir del dtype de pandas."""
    type_map = {
        "int64":   "INTEGER",
        "float64": "REAL",
        "bool":    "INTEGER",
        "object":  "TEXT",
        "datetime64[ns]": "TEXT",
    }
    cols_sql = []
    for col, dtype in zip(df.columns, df.dtypes):
        sql_type = type_map.get(str(dtype), "TEXT")
        cols_sql.append(f"    {col} {sql_type}")
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        + ",\n".join(cols_sql)
        + "\n);"
    )


# ─────────────────────────────────────────────
# CARGA PRINCIPAL
# ─────────────────────────────────────────────
def load_excel_to_sqlite() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_tables = 0
    total_rows   = 0

    for filename, sheets in EXCEL_FILES.items():
        filepath = BASE_DIR / filename
        if not filepath.exists():
            print(f"[AVISO] No encontrado: {filepath}")
            continue

        print(f"\n📂 Procesando: {filename}")
        xls = pd.ExcelFile(filepath, engine="openpyxl")

        for sheet_name, table_name in sheets.items():
            if sheet_name not in xls.sheet_names:
                print(f"  [AVISO] Hoja '{sheet_name}' no encontrada en {filename}")
                continue

            print(f"  → Hoja '{sheet_name}' → tabla '{table_name}' ...", end=" ")

            df = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                dtype=str,          # leer todo como texto primero
                keep_default_na=False,
            )
            df = clean_dataframe(df)

            # Crear tabla
            create_sql = infer_create_table(df, table_name)
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(create_sql)

            # Insertar filas en lotes de 1 000
            batch_size = 1_000
            placeholders = ", ".join(["?"] * len(df.columns))
            insert_sql = (
                f"INSERT INTO {table_name} "
                f"({', '.join(df.columns)}) VALUES ({placeholders})"
            )
            records = df.values.tolist()
            for i in range(0, len(records), batch_size):
                cursor.executemany(insert_sql, records[i : i + batch_size])

            conn.commit()
            print(f"{len(df):,} filas cargadas ✓")
            total_tables += 1
            total_rows   += len(df)

    conn.close()
    print(f"\n✅ Listo. {total_tables} tablas, {total_rows:,} filas → {DB_PATH}\n")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    load_excel_to_sqlite()
