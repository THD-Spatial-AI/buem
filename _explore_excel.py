"""Temporary script to explore Excel data structure."""
import pandas as pd

xl_path = "src/buem/data/buildings/tabula_building_child_features.xlsx"
xl = pd.ExcelFile(xl_path)

for sheet_name in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name)
    print(f"\n{'='*60}")
    print(f"Sheet: {sheet_name}")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Dtypes:\n{df.dtypes}")
    print(f"\nFirst 3 rows:\n{df.head(3).to_string()}")
    print(f"\nSample values for key columns:")
    for col in df.columns[:5]:
        print(f"  {col}: {df[col].unique()[:5]}")
