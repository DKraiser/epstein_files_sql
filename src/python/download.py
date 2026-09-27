"""Download selected files from a pinned Hugging Face dataset revision."""

from datetime import datetime, timezone
import defines
from pathlib import Path
from huggingface_hub import hf_hub_download
import hashlib
import json


def generate_manifest_header() -> dict: 
    return { 
        "repoId": defines.REPOSITORY,
        "sha256": defines.REVISION,
        "downloadDatetime": str(datetime.now(timezone.utc))
    }

def generate_manifest_items(paths: dict[str, list[Path]]) -> dict:
    manifest_items = dict()
    for (_, files) in paths.items():
        for path in files:
            file = path.read_bytes()
            sha256 = hashlib.sha256(file)
            size = len(file)
            lines = file.count(b"\n")
            
            manifest_items[str(path).removeprefix(str(f"{defines.PROJECT_DATASET_ROOT}/"))] = {
                "sha256": sha256.hexdigest(),
                "size": size,
                "lines": lines
            }
    return manifest_items

def download(paths: dict[str, list[str]], repo_id: str, repo_rev: str, target_dir: Path) -> None:
    for (_, files) in paths.items():
        for filename in files:
            path = hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=repo_rev,
                filename=filename,
                local_dir=target_dir,
            )
            print(f"Downloaded {path}")

def main() -> None:
    all_paths_remote = defines.REMOTE_FILES_PATHS.copy()
    all_paths_remote["administrative"] = ["README.md", "PROVENANCE.md", "LICENSE"]

    all_paths_local = defines.LOCAL_FILES_PATHS.copy()
    all_paths_local["administrative"] = [
        defines.PROJECT_DATASET_ROOT / "README.md", 
        defines.PROJECT_DATASET_ROOT / "PROVENANCE.md", 
        defines.PROJECT_DATASET_ROOT / "LICENSE"
    ]

    repo_id = defines.REPOSITORY
    repo_rev = defines.REVISION
    target_dir = defines.PROJECT_DATASET_ROOT

    download(all_paths_remote, repo_id, repo_rev, target_dir)

    manifest = generate_manifest_header() | generate_manifest_items(all_paths_local)
    with open(target_dir / "source_manifest.json", "w+") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)

if __name__ == "__main__":
    main()