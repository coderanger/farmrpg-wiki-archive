import csv
import datetime
import re
from pathlib import Path

import yaml
from git import Repo

ROOT_PATH = (Path(__file__) / "..").resolve()


def pull_views():
    # Parse the Git history for views over time.
    all_pages: set[str] = set()
    data: list[tuple[datetime.datetime, dict[str, int]]] = []
    repo = Repo(str(ROOT_PATH))
    for commit in repo.iter_commits("main"):
        views: dict[str, int] = {}
        for blob in commit.tree["wiki"].blobs:
            frontmatter = yaml.safe_load(
                re.split(
                    r"^---$", blob.data_stream.read().decode(), 1, flags=re.MULTILINE
                )[0]
            )
            views[frontmatter["name"]] = frontmatter["views"]
            all_pages.add(frontmatter["name"])
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
