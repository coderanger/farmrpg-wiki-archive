import csv
import datetime
import re
import sys
import traceback
import urllib.parse
from pathlib import Path

import httpx
import yaml
from git import Repo

ROOT_PATH = (Path(__file__) / "..").resolve()


def sync_page(
    c: httpx.Client, *, name: str, views: int, updated_datetime: str, **kwargs
):
    page_path = ROOT_PATH / "wiki" / f"{name.replace('/', '-')}.bbcode"
    frontmatter = {
        "name": name,
        "views": views,
        "updated_datetime": updated_datetime,
    }
    page_content = None

    # If the file already exists and the update timestamp matches, don't fetch it.
    if page_path.exists():
        existing = re.split(r"^---$", page_path.read_text(), 1, flags=re.MULTILINE)
        existing_frontmatter = yaml.safe_load(existing[0])
        if existing_frontmatter["updated_datetime"] == updated_datetime:
            # Page hasn't been updated, use the old content.
            page_content = existing[1].lstrip()

    if page_content is None:
        # Download the page content.
        print(f"Downloading {name}")
        resp = c.get(f"library/{urllib.parse.quote(name)}")
        resp.raise_for_status()
        page = resp.json()
        page_content = page[0]["content"]

    # Write out a bbcode file with YAML frontmatter.
    with page_path.open("w") as outf:
        yaml.dump(frontmatter, outf, sort_keys=True)
        outf.write("---\n")
        outf.write(page_content.replace("\r\n", "\n").replace("\r", "\n"))


def sync_wiki():
    with httpx.Client(
        base_url="https://farmrpg.com/api/", headers={"User-Agent": "wiki-archive/1.0"}
    ) as c:
        resp = c.get("library")
        resp.raise_for_status()
        errors = []
        for page in resp.json():
            try:
                sync_page(c, **page)
            except Exception:
                errors.append(page["name"])
                traceback.print_exc(file=sys.stdout)
        if errors:
            print("Errors fetching:")
            print("\n".join(errors))


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
    sync_wiki()
    pull_views()
