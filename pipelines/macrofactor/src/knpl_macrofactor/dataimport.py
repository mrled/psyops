import logging

import pandas as pd
from psycopg2 import sql

from knpl_macrofactor.db import get_connection

# Original schemas, unchanged
SCHEMA_MAP = {
    "calories_macros": {
        "Date": "DATE PRIMARY KEY",
        "Calories__kcal": "INTEGER",
        "Protein__g": "FLOAT",
        "Fat__g": "FLOAT",
        "Carbs__g": "FLOAT",
    },
    "micronutrients": {
        "Date": "DATE PRIMARY KEY",
        "Fiber__g": "FLOAT",
        "Starch__g": "FLOAT",
        "Sugars__g": "FLOAT",
        "Sugars_Added__g": "FLOAT",
        "Cysteine__g": "FLOAT",
        "Histidine__g": "FLOAT",
        "Isoleucine__g": "FLOAT",
        "Leucine__g": "FLOAT",
        "Lysine__g": "FLOAT",
        "Methionine__g": "FLOAT",
        "Phenylalanine__g": "FLOAT",
        "Threonine__g": "FLOAT",
        "Tryptophan__g": "FLOAT",
        "Tyrosine__g": "FLOAT",
        "Valine__g": "FLOAT",
        "Monounsaturated_Fat__g": "FLOAT",
        "Polyunsaturated_Fat__g": "FLOAT",
        "Omega_3__g": "FLOAT",
        "Omega_3_ALA__g": "FLOAT",
        "Omega_3_EPA__g": "FLOAT",
        "Omega_3_DHA__g": "FLOAT",
        "Omega_6__g": "FLOAT",
        "Saturated_Fat__g": "FLOAT",
        "Trans_Fat__g": "FLOAT",
        "Vitamin_A__mcg": "FLOAT",
        "B1__Thiamine__mg": "FLOAT",
        "B2__Riboflavin__mg": "FLOAT",
        "B3__Niacin__mg": "FLOAT",
        "B5__Pantothenic_Acid__mg": "FLOAT",
        "B6__Pyridoxine__mg": "FLOAT",
        "B12__Cobalamin__mcg": "FLOAT",
        "Folate__mcg": "FLOAT",
        "Vitamin_C__mg": "FLOAT",
        "Vitamin_D__mcg": "FLOAT",
        "Vitamin_E__mg": "FLOAT",
        "Vitamin_K__mcg": "FLOAT",
        "Calcium__mg": "FLOAT",
        "Copper__mg": "FLOAT",
        "Iron__mg": "FLOAT",
        "Magnesium__mg": "FLOAT",
        "Manganese__mg": "FLOAT",
        "Phosphorus__mg": "FLOAT",
        "Potassium__mg": "FLOAT",
        "Selenium__mcg": "FLOAT",
        "Sodium__mg": "FLOAT",
        "Zinc__mg": "FLOAT",
        "Water__g": "FLOAT",
        "Choline__mg": "FLOAT",
        "Cholesterol__mg": "FLOAT",
        "Caffeine__mg": "FLOAT",
        "Alcohol__g": "FLOAT",
    },
    "scale_weight": {
        "Date": "DATE PRIMARY KEY",
        "Weight__lbs": "FLOAT",
        "Fat_Percent": "FLOAT",
    },
    "body_metrics": {
        "Date": "DATE PRIMARY KEY",
        "Visual_Body_Fat_Assessment": "FLOAT",
        "Shoulders__in": "FLOAT",
        "Chest__in": "FLOAT",
        "Bust__in": "FLOAT",
        "Neck__in": "FLOAT",
        "Hips__in": "FLOAT",
        "Waist__in": "FLOAT",
        "Left_Bicep__in": "FLOAT",
        "Right_Bicep__in": "FLOAT",
        "Left_Forearm__in": "FLOAT",
        "Right_Forearm__in": "FLOAT",
        "Left_Wrist__in": "FLOAT",
        "Right_Wrist__in": "FLOAT",
        "Left_Calf__in": "FLOAT",
        "Right_Calf__in": "FLOAT",
        "Left_Thigh__in": "FLOAT",
        "Right_Thigh__in": "FLOAT",
        "Left_Ankle__in": "FLOAT",
        "Right_Ankle__in": "FLOAT",
    },
    "weight_trend": {
        "Date": "DATE PRIMARY KEY",
        "Trend_Weight__lbs": "FLOAT",
    },
    "expenditure": {
        "Date": "DATE PRIMARY KEY",
        "Expenditure": "FLOAT",
    },
    "steps": {
        "Date": "DATE PRIMARY KEY",
        "Steps": "INTEGER",
    },
}

SHEET_TO_TABLE = {
    "Calories & Macros": "calories_macros",
    "Micronutrients": "micronutrients",
    "Scale weight": "scale_weight",
    "Body Metrics": "body_metrics",
    "Weight Trend": "weight_trend",
    "Expenditure": "expenditure",
    "Steps": "steps",
}

def ensure_table_and_columns(cursor, table_name, columns_map):
    """
    Creates the table if it doesn't exist, sets up the primary key,
    and adds columns that may be missing.
    """
    pk_cols = [col for col, dtype in columns_map.items() if "PRIMARY KEY" in dtype]
    col_defs = []
    for col, dtype in columns_map.items():
        base_type = dtype.replace("PRIMARY KEY", "").strip()
        col_defs.append(f"{col} {base_type}")
    pk_clause = f", PRIMARY KEY ({', '.join(pk_cols)})" if pk_cols else ""
    create_sql = (
        f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)}{pk_clause});"
    )
    logging.debug(
        "Ensuring table '%s' exists with columns: %s",
        table_name,
        list(columns_map.keys()),
    )
    cursor.execute(create_sql)

    # Add columns that might be missing
    for col, dtype in columns_map.items():
        base_type = dtype.replace("PRIMARY KEY", "").strip()
        alter_sql = (
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col} {base_type};"
        )
        cursor.execute(alter_sql)


def import_xlsx(args):
    """
    Reads an Excel file from args.xlsx_file, creates tables if needed
    for each recognized sheet, and upserts the data.
    """
    logging.debug("Importing Excel file '%s'.", args.xlsx_file)
    with get_connection(args) as conn:
        with conn.cursor() as cursor:
            # Make sure macrofactor_files table exists
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS macrofactor_files (
                    file_key TEXT PRIMARY KEY,
                    imported_at TIMESTAMP DEFAULT NOW()
                );
            """
            )

            xls = pd.ExcelFile(args.xlsx_file)

            # For each sheet->table mapping, if that sheet is present, create/update table and import data
            for sheet_name, table_name in SHEET_TO_TABLE.items():
                if sheet_name not in xls.sheet_names:
                    logging.warning("Sheet '%s' not found; skipping.", sheet_name)
                    continue

                if table_name not in SCHEMA_MAP:
                    logging.warning("No schema defined for table '%s'; skipping.", table_name)
                    continue

                # Load the sheet
                df = xls.parse(sheet_name)

                # Normalize columns
                def normalize(col):
                    return (
                        col.strip()
                           .replace(" ", "_")
                           .replace(",", "")
                           .replace("(", "")
                           .replace(")", "")
                           .replace("__", "_")  # unify repeated underscores
                           .replace("_g", "__g")
                           .replace("_in", "__in")
                           .replace("_lbs", "__lbs")
                           .replace("_mcg", "__mcg")
                           .replace("_mg", "__mg")
                    )

                df.columns = [normalize(c) for c in df.columns]

                # Ensure the table and columns
                ensure_table_and_columns(cursor, table_name, SCHEMA_MAP[table_name])

                # Prepare upsert statement
                cols = list(df.columns)
                placeholders = ", ".join(["%s"] * len(cols))
                col_list = ", ".join(cols)
                update_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c != "Date"])

                upsert_sql = sql.SQL(
                    f"""
                    INSERT INTO {table_name} ({col_list})
                    VALUES ({placeholders})
                    ON CONFLICT (Date)
                    DO UPDATE SET {update_clause};
                """
                )

                row_count = 0
                for _, row_data in df.iterrows():
                    row_vals = [None if pd.isna(x) else x for x in row_data.values]
                    cursor.execute(upsert_sql, row_vals)
                    row_count += 1

                logging.info("Imported/updated %d rows into '%s'.", row_count, table_name)

        conn.commit()
    logging.debug("Finished importing '%s'.", args.xlsx_file)
