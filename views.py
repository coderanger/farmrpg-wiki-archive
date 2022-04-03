import csv
import datetime
import itertools
import json
import os
from pathlib import Path

from git.repo import Repo

ROOT_PATH = (Path(__file__) / "..").resolve()
PAGE_VIEWS_IGNORE = [
    s.strip() for s in os.environ.get("PAGE_VIEWS_IGNORE", "").split(",") if s.strip()
]

ViewsData = list[tuple[dict[str, datetime.datetime], dict[str, int]]]


def write_csv(
    data: ViewsData,
    path: Path,
    all_pages: set[str],
):
    with path.open("w") as outf:
        writer = csv.DictWriter(outf, list(data[0][0].keys()) + sorted(all_pages))
        writer.writeheader()
        for timestamps, views in data:
            writer.writerow(
                {
                    **{label: ts.isoformat() for label, ts in timestamps.items()},
                    **views,
                }
            )


def write_flat_csv(
    data: ViewsData,
    path: Path,
):
    with path.open("w") as outf:
        writer = csv.DictWriter(outf, list(data[0][0].keys()) + ["Page", "Views"])
        writer.writeheader()
        for timestamps, views in data:
            for page, page_views in views.items():
                writer.writerow(
                    {
                        **{label: ts.isoformat() for label, ts in timestamps.items()},
                        "Page": page,
                        "Views": page_views,
                    }
                )


def pull_views():
    # Parse the Git history for views over time.
    all_pages: set[str] = set()
    data: ViewsData = []
    repo = Repo(str(ROOT_PATH))
    for commit in repo.iter_commits("main"):
        message = (
            commit.message
            if isinstance(commit.message, str)
            else commit.message.decode()
        )
        if "Latest data:" not in message:
            continue
        try:
            blob = commit.tree / "views" / "current.json"  # type: ignore
        except KeyError:
            # Too early, ignoring.
            continue
        views: dict[str, int] = json.load(blob.data_stream)
        for ignore in PAGE_VIEWS_IGNORE:
            views.pop(ignore, None)
        all_pages |= views.keys()
        data.append(({"Timestamp": commit.authored_datetime}, views))
    assert "Timestamp" not in all_pages
    data.sort(key=lambda d: d[0]["Timestamp"])
    # Generate a CSV file with all view data.
    # Columns are all the pages, rows are timestamps.
    write_csv(data, ROOT_PATH / "views" / "views.csv", all_pages)
    # Generate a CSV file with the view diffs.
    diffs: ViewsData = []
    for ((timestamp1, views1), (timestamp2, views2)) in itertools.pairwise(data):
        view_diff = {
            p: views2.get(p, 0) - views1.get(p, 0)
            for p in views1.keys() | views2.keys()
        }
        diffs.append(
            (
                {"From": timestamp1["Timestamp"], "To": timestamp2["Timestamp"]},
                view_diff,
            )
        )
    # Diffs but by day (roughly).
    write_csv(diffs, ROOT_PATH / "views" / "diffs.csv", all_pages)
    # Variant files for each that are in a simpler layout.
    write_flat_csv(data, ROOT_PATH / "views" / "flat_views.csv")
    write_flat_csv(diffs, ROOT_PATH / "views" / "flat_diffs.csv")


if __name__ == "__main__":
    pull_views()
