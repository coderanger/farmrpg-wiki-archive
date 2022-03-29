import re
import sys
import traceback
import urllib.parse
from pathlib import Path

import httpx
import yaml

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


if __name__ == "__main__":
    sync_wiki()
