import pandas as pd
import json
import uuid
import re
from collections import Counter

df = pd.read_csv(
    "../data/cities_dataset.csv"
)

print("=" * 80)
print("DATASET PROFILE")
print("=" * 80)

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print()


# =============================================================================
# HELPERS
# =============================================================================

def detect_base_type(series):

    non_null = series.dropna()

    if len(non_null) == 0:
        return "unknown"

    sample = str(non_null.iloc[0])

    # UUID
    try:
        uuid.UUID(sample)
        return "uuid"
    except:
        pass

    # JSON
    if sample.startswith("{") or sample.startswith("["):
        return "json"

    # INTEGER
    if pd.api.types.is_integer_dtype(non_null):
        return "integer"

    # FLOAT
    if pd.api.types.is_float_dtype(non_null):
        return "float"

    return "string"


def analyze_string(series):

    non_null = series.dropna().astype(str)

    lengths = non_null.str.len()

    print(f"MAX LENGTH: {lengths.max()}")
    print(f"AVG LENGTH: {round(lengths.mean(), 2)}")

    unique_count = non_null.nunique()

    print(f"UNIQUE COUNT: {unique_count}")

    if unique_count <= 20:
        print("VALUES:")

        for val in sorted(non_null.unique()):
            print(f"  - {val}")


def analyze_integer(series):

    non_null = series.dropna()

    print(f"MIN: {non_null.min()}")
    print(f"MAX: {non_null.max()}")

    unique_vals = sorted(non_null.unique())

    print(f"UNIQUE COUNT: {len(unique_vals)}")

    if len(unique_vals) <= 20:
        print(f"VALUES: {unique_vals}")


def analyze_float(series):

    non_null = series.dropna()

    print(f"MIN: {non_null.min()}")
    print(f"MAX: {non_null.max()}")

    decimal_places = (
        non_null.astype(str)
        .str.extract(r'\.(\d+)')[0]
        .dropna()
        .str.len()
    )

    if len(decimal_places) > 0:
        print(f"MAX DECIMAL PLACES: {decimal_places.max()}")


def analyze_json(series):

    non_null = series.dropna()

    parsed_values = []

    for raw in non_null:

        try:
            parsed = json.loads(str(raw).replace("'", '"'))
            parsed_values.append(parsed)

        except Exception as e:
            print(f"JSON PARSE ERROR: {e}")
            return

    sample = parsed_values[0]

    # =========================================================================
    # JSON OBJECT
    # =========================================================================

    if isinstance(sample, dict):

        print("JSON TYPE: object")

        all_keys = set()

        for obj in parsed_values:
            all_keys.update(obj.keys())

        print(f"TOP LEVEL KEY COUNT: {len(all_keys)}")
        print(f"TOP LEVEL KEYS: {sorted(all_keys)}")

        first_value = next(iter(sample.values()))

        # nested object
        if isinstance(first_value, dict):

            nested_keys = set()

            for obj in parsed_values:

                for nested in obj.values():

                    if isinstance(nested, dict):
                        nested_keys.update(nested.keys())

            print(f"NESTED KEY COUNT: {len(nested_keys)}")
            print(f"NESTED KEYS: {sorted(nested_keys)}")

    # =========================================================================
    # JSON ARRAY
    # =========================================================================

    elif isinstance(sample, list):

        print("JSON TYPE: array")

        array_lengths = []

        all_elements = []

        for arr in parsed_values:

            array_lengths.append(len(arr))

            all_elements.extend(arr)

        print(f"MIN ARRAY LENGTH: {min(array_lengths)}")
        print(f"MAX ARRAY LENGTH: {max(array_lengths)}")

        counter = Counter(all_elements)

        print(f"UNIQUE ELEMENT COUNT: {len(counter)}")

        print("ELEMENT VALUES:")

        for value, count in sorted(counter.items()):
            print(f"  - {value} ({count})")


# =============================================================================
# COLUMN ANALYSIS
# =============================================================================

for col in df.columns:

    print("-" * 80)
    print(f"COLUMN: {col}")

    series = df[col]

    print(f"NULLABLE: {series.isnull().any()}")
    print(f"NULL COUNT: {series.isnull().sum()}")

    duplicates = len(series) - series.nunique(dropna=False)
    print(f"DUPLICATES: {duplicates}")

    base_type = detect_base_type(series)

    print(f"TYPE: {base_type}")

    # =========================================================================
    # UUID
    # =========================================================================

    if base_type == "uuid":

        unique_count = series.nunique(dropna=True)

        print(f"UNIQUE COUNT: {unique_count}")

        if unique_count == len(series):
            print("ALL VALUES UNIQUE: True")

    # =========================================================================
    # STRING
    # =========================================================================

    elif base_type == "string":

        analyze_string(series)

    # =========================================================================
    # INTEGER
    # =========================================================================

    elif base_type == "integer":

        analyze_integer(series)

    # =========================================================================
    # FLOAT
    # =========================================================================

    elif base_type == "float":

        analyze_float(series)

    # =========================================================================
    # JSON
    # =========================================================================

    elif base_type == "json":

        analyze_json(series)

print("-" * 80)


# =============================================================================
# SHARED INTEGER SCALE DETECTION
# =============================================================================

print()
print("=" * 80)
print("SHARED INTEGER SCALE ANALYSIS")
print("=" * 80)

integer_cols = []

for col in df.columns:

    if detect_base_type(df[col]) == "integer":

        unique_vals = sorted(df[col].dropna().unique())

        if len(unique_vals) <= 10:
            integer_cols.append((col, unique_vals))

groups = {}

for col, vals in integer_cols:

    key = tuple(vals)

    if key not in groups:
        groups[key] = []

    groups[key].append(col)

for vals, cols in groups.items():

    print()
    print(f"SCALE VALUES: {list(vals)}")
    print(f"COLUMN COUNT: {len(cols)}")

    for col in cols:
        print(f"  - {col}")