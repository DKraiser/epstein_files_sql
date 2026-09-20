import argparse
import polars as pl

import defines


def overview(path: str) -> None:
    df = pl.read_parquet(path)

    print("Shape:", df.shape)
    print("\nSchema:")
    print(df.schema)

    print("\nFirst 5 rows:")
    print(df.head())

def main():
    pl.Config.set_tbl_cols(-1)

    for path in defines.DEFAULT_FILES_PATHS: 
        print('=' * 10 + path[0].title().split('/')[-1] + '=' * 10)
        overview(f"{defines.PROJECT_ROOT}/data/{path[0]}")
        print()

if __name__ == "__main__":
    main()