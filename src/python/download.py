"""Download selected files from a pinned Hugging Face dataset revision."""

import argparse
import defines
from huggingface_hub import hf_hub_download


def main() -> None:
    paths = defines.FULL_FILES_PATHS

    for group in paths:
        for filename in group:
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