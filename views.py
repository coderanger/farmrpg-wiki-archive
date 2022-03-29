import csv
import datetime
import json
from pathlib import Path

from git import Repo

ROOT_PATH = (Path(__file__) / "..").resolve()


def pull_views():
    # Parse the Git history for views over time.
    all_pages: set[str] = set()
    data: list[tuple[datetime.datetime, dict[str, int]]] = []
    repo = Repo(str(ROOT_PATH))
    for commit in repo.iter_commits("main"):
        if "Latest data:" not in commit.message:
            continue
        try:
            blob = commit.tree / "views" / "current.json"
        except KeyError:
            # Too early, ignoring.
            continue
        views: dict[str, int] = json.load(blob.data_stream)
        all_pages |= views.keys()
        data.append((commit.authored_datetime, views))
    assert "Timestamp" not in all_pages
    # Generate a CSV file with all view data.
    # Columns are all the pages, rows are timestamps.
    csv_path = ROOT_PATH / "views" / "views.csv"
    with csv_path.open("w") as outf:
        writer = csv.DictWriter(outf, ["Timestamp"] + sorted(all_pages))
        writer.writeheader()
        for timestamp, views in data:
            views["Timestamp"] = timestamp.isoformat()
            writer.writerow(views)


if __name__ == "__main__":
    pull_views()
