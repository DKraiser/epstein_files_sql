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
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="download every path in FULL_FILES")
    args = parser.parse_args()

    paths = defines.FULL_FILES_PATHS if args.full else defines.DEFAULT_FILES_PATHS
    if args.full and not paths:
        parser.error("Add the files you need to FULL_FILES before using --full.")

    pl.Config.set_tbl_cols(-1)

    for path in paths: 
        print('=' * 10 + path[0].title().split('/')[-1] + '=' * 10)
        overview(f"{defines.PROJECT_ROOT}/data/{path}")
        print()

if __name__ == "__main__":
    main()