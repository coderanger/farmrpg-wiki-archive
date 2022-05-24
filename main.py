import json
import re
import sys
import traceback
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import yaml

ROOT_PATH = (Path(__file__) / "..").resolve()

client = httpx.Client(
    base_url="https://farmrpg.com/api/", headers={"User-Agent": "wiki-archive/1.0"}
)


def sync_page(name: str, views: int, updated_datetime: str, **kwargs):
    page_path = ROOT_PATH / "wiki" / f"{name.replace('/', '-')}.bbcode"
    frontmatter = {
        "name": name,
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
            # TODO After the views removal propgates, this can just early out instead.

    if page_content is None:
        # Download the page content.
        print(f"Downloading {name}")
        resp = client.get(f"library/{urllib.parse.quote(name)}")
        resp.raise_for_status()
        page = resp.json()
        page_content = page[0]["content"]

    # Write out a bbcode file with YAML frontmatter.
    with page_path.open("w") as outf:
        yaml.dump(frontmatter, outf, sort_keys=True)
        outf.write("---\n")
        outf.write(page_content.replace("\r\n", "\n").replace("\r", "\n"))


def sync_wiki():
    resp = client.get("library")
    resp.raise_for_status()
    errors = []
    views = {}
    for page in resp.json():
        views[page["name"]] = page["views"]
        try:
            sync_page(**page)
        except Exception:
            errors.append(page["name"])
            traceback.print_exc(file=sys.stdout)
    all_pages = {name.replace("/", "-") for name in views}
    now = datetime.now(tz=ZoneInfo("America/Chicago"))
    for page_path in ROOT_PATH.glob("wiki/*.bbcode"):
        if page_path.stem in all_pages:
            # Filter any page that still exists in the API.
            continue
        # Mark the page as deleted.
        existing = re.split(r"^---$", page_path.read_text(), 1, flags=re.MULTILINE)
        frontmatter = yaml.safe_load(existing[0])
        if "deleted_datetime" not in frontmatter:
            frontmatter["deleted_datetime"] = now.isoformat()
            with page_path.open("w") as outf:
                yaml.dump(frontmatter, outf, sort_keys=True)
                outf.write("---")
                outf.write(existing[1])
    with (ROOT_PATH / "views" / "current.json").open("w") as outf:
        json.dump(views, outf, indent=2, sort_keys=True)
    if errors:
        print("Errors fetching:")
        print("\n".join(errors))


def sync_tower():
    resp = client.get("towercounts")
    resp.raise_for_status()
    tower = {i + 1: 0 for i in range(100)}
    for row in resp.json():
        tower[row["tower"]] = row["count"]
    with (ROOT_PATH / "tower" / "current.json").open("w") as outf:
        json.dump(tower, outf, indent=2, sort_keys=True)


if __name__ == "__main__":
    sync_wiki()
    sync_tower()
