import polars as pl
from pathlib import Path
from defines import LOCAL_FILES_PATHS


def overview(path: Path) -> None:
    df = pl.read_parquet(path)

    print(df.schema)
    # print(df.shape)
    print("\nFirst 5 rows:")
    print(df.head())

def main():
    paths = LOCAL_FILES_PATHS
  
    pl.Config.set_tbl_cols(-1)

    for (category, path_collection) in paths.items(): 
        print('=' * 10 + category + '=' * 10)
        overview(path_collection[0])
        print()

if __name__ == "__main__":
    main()