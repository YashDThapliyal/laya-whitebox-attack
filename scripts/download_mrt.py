"""Download the selected (deduplicated) MRT transcripts. Bounded: fixed file list, 3 retries each."""
import json
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import hf_hub_download

paths = json.load(open("raw/mrt_selected.json"))

def get(p):
    for _ in range(3):
        try:
            hf_hub_download("ScaleAI/mrt", p, repo_type="dataset", local_dir="raw/mrt")
            return True
        except Exception as e:
            err = e
    print("FAIL", p, err)
    return False

with ThreadPoolExecutor(16) as ex:
    ok = sum(ex.map(get, paths))
print("downloaded", ok, "/", len(paths))
