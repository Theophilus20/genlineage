"""Seed the demo from the doc's 3-minute flow:

  1. "30-sec teaser for a coffee brand" on main — the gate rejects at least
     one frame, retries, and the DAG grows.
  2. Branch "matcha-variant", remixed from main with only the subject
     changed — shared steps dedup-reference the store.

Run with the API up:  python tools/seed_demo.py [http://localhost:8000]
"""
import sys
import time

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def wait(job_id: str) -> dict:
    while True:
        job = httpx.get(f"{API}/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.4)


def main():
    p = httpx.post(f"{API}/api/projects", json={"name": "Coffee Teaser"}).json()
    print("project:", p["id"])

    j1 = httpx.post(f"{API}/api/projects/{p['id']}/jobs",
                    json={"brief": "30-sec teaser for a coffee brand"}).json()
    job1 = wait(j1["id"])
    retries = sum(1 for e in job1["events"] if e["event"] == "step.retry")
    print(f"main: {job1['status']} — quality-gate retries: {retries}")

    j2 = httpx.post(f"{API}/api/projects/{p['id']}/jobs",
                    json={"brief": "30-sec teaser for a matcha brand",
                          "branch": "matcha-variant",
                          "base_branch": "main"}).json()
    job2 = wait(j2["id"])
    reused = sum(1 for e in job2["events"] if e["event"] == "step.reused")
    print(f"matcha-variant: {job2['status']} — dedup-referenced steps: {reused}")

    dag = httpx.get(f"{API}/api/projects/{p['id']}/dag").json()
    print(f"DAG: {len(dag['nodes'])} nodes / {len(dag['edges'])} edges")
    print(f"Open the studio and select “{'Coffee Teaser'}”.")


if __name__ == "__main__":
    main()
