import csv
import datetime
import itertools
import json
import re
import zoneinfo
from pathlib import Path

import yaml
from git.repo import Repo

ROOT_PATH = (Path(__file__) / "..").resolve()
SERVER_TIME_ZONE = zoneinfo.ZoneInfo("America/Chicago")

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


def is_page_deleted(page: str):
    page_path = ROOT_PATH / "wiki" / f"{page}.bbcode"
    if not page_path.exists():
        return False
    page_data = re.split(r"^---$", page_path.read_text(), 1, flags=re.MULTILINE)
    page_frontmatter = yaml.safe_load(page_data[0])
    return "deleted_datetime" in page_frontmatter


def write_unviewed_pages(data: ViewsData, path: Path, all_pages: set[str]):
    # Find the first row from the last 30 days.
    now = datetime.datetime.now(zoneinfo.ZoneInfo("UTC"))
    limit_ts = now - datetime.timedelta(days=30)
    first_row = None
    for timestamps, views in data:
        if timestamps["Timestamp"] >= limit_ts:
            first_row = views
            break
    else:
        raise Exception("Unable to find first row?")
    last_row = data[-1][1]

    # Find the diffs.
    diffs = {page: last_row.get(page, 0) - first_row.get(page, 0) for page in all_pages}
    unviewed = {
        page: views
        for page, views in diffs.items()
        if views <= 10 and not is_page_deleted(page)
    }

    with path.open("w") as outf:
        outf.write(
            f"Pages with 10 views or fewer in the last 30 days. Updated at {now.isoformat()}\n----\n"
        )

        for page, views in sorted(unviewed.items(), key=lambda kv: (kv[1], kv[0])):
            outf.write(f"{page}: {views}\n")


def pull_views():
    # Parse the Git history for views over time.
    all_pages: set[str] = set()
    data: ViewsData = []
    repo = Repo(str(ROOT_PATH))
    next_ts = None
    for commit in repo.iter_commits("main"):
        message = (
            commit.message
            if isinstance(commit.message, str)
            else commit.message.decode()
        )
        if "Latest data:" not in message:
            continue
        # Only pull the "first" (actually last because reverse order) commit from each day.
        # This is purely to reduce the file size on views.csv, it's too big for GitHub at
        # full resolution, so cut it to a single row per day.
        if next_ts is not None and commit.authored_datetime >= next_ts:
            continue
        # Advance (backwards) to the start of this day.
        next_ts = commit.authored_datetime.astimezone(SERVER_TIME_ZONE).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        try:
            blob = commit.tree / "views" / "current.json"  # type: ignore
        except KeyError:
            # Too early, ignoring.
            continue
        views: dict[str, int] = json.load(blob.data_stream)
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
    write_csv(diffs, ROOT_PATH / "views" / "diffs.csv", all_pages)
    write_unviewed_pages(data, ROOT_PATH / "views" / "unviewed_pages.txt", all_pages)
    # Variant files for each that are in a simpler layout.
    # write_flat_csv(data, ROOT_PATH / "views" / "flat_views.csv")
    # write_flat_csv(diffs, ROOT_PATH / "views" / "flat_diffs.csv")


if __name__ == "__main__":
    pull_views()
