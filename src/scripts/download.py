"""Download selected files from a pinned Hugging Face dataset revision."""

import argparse
import defines
from huggingface_hub import hf_hub_download

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="download every path in FULL_FILES")
    args = parser.parse_args()

    paths = defines.FULL_FILES_PATHS if args.full else defines.DEFAULT_FILES_PATHS
    if args.full and not paths:
        parser.error("Add the files you need to FULL_FILES before using --full.")

    for filename in paths:
        path = hf_hub_download(
            repo_id=defines.REPOSITORY,
            repo_type="dataset",
            revision=defines.REVISION,
            filename=filename,
            local_dir=f"{defines.PROJECT_ROOT}/data",
        )
        print(f"Downloaded {path}")


if __name__ == "__main__":
    main()
