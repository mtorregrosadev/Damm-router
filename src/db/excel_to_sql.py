import re
import pandas as pd
from pathlib import Path

try:
    from src.db.mongo import get_db
except ImportError:
    from mongo import get_db

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

EXCEL_FILES = {
    PROJECT_ROOT / "BD/Hackaton.xlsx": {
        "Detalle entrega":      "detalle_entrega",
        "Cabecera Transporte":  "cabecera_transporte",
        "Direcciones":          "direcciones",
        "ZONAS":                "zonas",
        "Materiales zubic":     "materiales_zubic",
    },
    PROJECT_ROOT / "BD/Horarios Entrega.XLSX": {
        "Sheet1": "horarios_entrega",
    },
}


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def normalize_column(name: str, seen: dict) -> str:
    """Convierte un nombre de columna a snake_case válido.
    Desambigua duplicados añadiendo _2, _3, …"""
    if name is None:
        name = "col"
    name = str(name).strip()
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    name = name.lower() or "col"

    base = name
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count > 1:
        name = f"{base}_{count}"

    return name


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict = {}
    new_cols = [normalize_column(c, seen) for c in df.columns]
    df.columns = new_cols
    return df


# ─────────────────────────────────────────────
# CARGA PRINCIPAL
# ─────────────────────────────────────────────
def load_excel_to_sqlite() -> None:
    mdb = get_db()

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

            print(f"  → Hoja '{sheet_name}' → col·lecció '{table_name}' ...", end=" ")

            df = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                dtype=str,
                keep_default_na=False,
            )
            df = clean_dataframe(df)

            col = mdb[table_name]
            col.drop()
            docs = df.to_dict(orient="records")
            if docs:
                col.insert_many(docs)

            print(f"{len(df):,} files carregades ✓ (MongoDB)")
            total_tables += 1
            total_rows   += len(df)

    print(f"\n✅ Llest. {total_tables} col·leccions, {total_rows:,} documents → MongoDB\n")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    load_excel_to_sqlite()
