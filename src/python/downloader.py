"""Download selected files from a pinned Hugging Face dataset revision."""

from datetime import datetime, timezone
from shared.dataset_passport import REPOSITORY, REVISION, PROJECT_DATASET_ROOT, LOCAL_FILES_PATHS, REMOTE_FILES_PATHS
from pathlib import Path
from huggingface_hub import hf_hub_download
import hashlib
import json
import polars as pl

def generate_manifest_header() -> dict: 
    return { 
        "repoId": REPOSITORY,
        "sha256": REVISION,
        "downloadDatetime": str(datetime.now(timezone.utc))
    }

def generate_manifest_items(paths: dict[str, list[Path]]) -> dict:
    manifest_items = dict()
    for (_, files) in paths.items():
        for path in files:
            file = path.read_bytes()
            sha256 = hashlib.sha256(file)
            size = len(file)
            lines = pl.scan_parquet(path).select(pl.len()).collect().item() if path.name.split('.')[-1] == "parquet" else file.count(b"\n")
            
            manifest_items[str(path).removeprefix(str(f"{PROJECT_DATASET_ROOT}/"))] = {
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
    all_paths_remote = REMOTE_FILES_PATHS.copy()
    all_paths_remote["administrative"] = ["README.md", "PROVENANCE.md", "LICENSE"]

    all_paths_local = LOCAL_FILES_PATHS.copy()
    all_paths_local["administrative"] = [
        PROJECT_DATASET_ROOT / "README.md", 
        PROJECT_DATASET_ROOT / "PROVENANCE.md", 
        PROJECT_DATASET_ROOT / "LICENSE"
    ]

    repo_id = REPOSITORY
    repo_rev = REVISION
    target_dir = PROJECT_DATASET_ROOT

    download(all_paths_remote, repo_id, repo_rev, target_dir)

    manifest = generate_manifest_header() | generate_manifest_items(all_paths_local)
    with open(target_dir / "source_manifest.json", "w+") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)

if __name__ == "__main__":
    main()