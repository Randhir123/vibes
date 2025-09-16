"""Download and analyze IMDb movie rating distribution.

This script downloads the IMDb datasets required to analyze the
average rating distribution for movies and prints a summary of the
results.  It keeps the downloaded files inside a local ``data``
directory that lives next to this script, so repeated executions do not
redownload the large TSV files.
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import math
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

DATASETS: Dict[str, str] = {
    "title.basics.tsv.gz": "https://datasets.imdbws.com/title.basics.tsv.gz",
    "title.ratings.tsv.gz": "https://datasets.imdbws.com/title.ratings.tsv.gz",
}

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def download_file(url: str, destination: Path) -> None:
    """Download ``url`` to ``destination`` using a browser-style user agent."""

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except URLError as exc:  # pragma: no cover - network errors are user-facing
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def ensure_datasets(force_download: bool = False) -> None:
    """Ensure that all of the required IMDb datasets exist locally."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in DATASETS.items():
        destination = DATA_DIR / filename
        if destination.exists() and not force_download:
            print(f"✔ Dataset already present: {filename}")
            continue

        if destination.exists():
            print(f"↻ Redownloading {filename}...")
        else:
            print(f"↓ Downloading {filename}...")
        download_file(url, destination)
        print(f"  Saved to {destination}")


def iter_tsv(path: Path) -> Iterable[Dict[str, str]]:
    """Yield rows from a gzipped TSV file as dictionaries."""

    with gzip.open(path, mode="rt", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            yield row


def collect_movie_ids(basics_path: Path) -> set[str]:
    """Return the IMDb identifiers for titles that are feature films."""

    movie_ids: set[str] = set()
    for row in iter_tsv(basics_path):
        if row.get("titleType") != "movie":
            continue
        tconst = row.get("tconst")
        if not tconst:
            continue
        movie_ids.add(tconst)
    return movie_ids


def analyze_ratings(ratings_path: Path, movie_ids: set[str]) -> Tuple[int, collections.Counter[int], collections.Counter[str], int]:
    """Analyze rating information for the provided movie identifiers."""

    integer_distribution: collections.Counter[int] = collections.Counter()
    precise_distribution: collections.Counter[str] = collections.Counter()
    movie_count = 0
    total_votes = 0

    for row in iter_tsv(ratings_path):
        tconst = row.get("tconst")
        if not tconst or tconst not in movie_ids:
            continue
        rating_str = row.get("averageRating")
        votes_str = row.get("numVotes")
        if not rating_str or rating_str == "\\N" or not votes_str or votes_str == "\\N":
            continue

        movie_count += 1
        total_votes += int(votes_str)
        precise_distribution[rating_str] += 1

        rating = float(rating_str)
        bucket = int(math.floor(rating))
        integer_distribution[bucket] += 1

    return movie_count, integer_distribution, precise_distribution, total_votes


def print_summary(movie_count: int, integer_distribution: collections.Counter[int], precise_distribution: collections.Counter[str]) -> None:
    """Print a textual summary of the rating distributions."""

    if movie_count == 0:
        print("No movies with ratings were found.")
        return

    print("\n=== IMDb movie rating distribution (integer buckets) ===")
    print("Rating  Movies  Percent")
    for rating in sorted(integer_distribution):
        count = integer_distribution[rating]
        percent = 100.0 * count / movie_count
        print(f"{rating:>6}  {count:>6}  {percent:6.2f}%")

    print("\n=== Top precise average ratings (0.1 increments) ===")
    print("Rating  Movies  Percent")
    for rating_str, count in sorted(
        precise_distribution.items(), key=lambda item: (-item[1], float(item[0]))
    )[:10]:
        percent = 100.0 * count / movie_count
        print(f"{rating_str:>6}  {count:>6}  {percent:6.2f}%")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Redownload the IMDb datasets even if they already exist locally.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ensure_datasets(force_download=args.force_download)

    basics_path = DATA_DIR / "title.basics.tsv.gz"
    ratings_path = DATA_DIR / "title.ratings.tsv.gz"

    print("Collecting movie identifiers...")
    movie_ids = collect_movie_ids(basics_path)
    print(f"Found {len(movie_ids):,} movie titles with metadata.")

    print("Analyzing rating information...")
    movie_count, integer_distribution, precise_distribution, total_votes = analyze_ratings(
        ratings_path, movie_ids
    )
    print(f"Movies with at least one rating: {movie_count:,}")
    print(f"Aggregate number of votes across these movies: {total_votes:,}")

    print_summary(movie_count, integer_distribution, precise_distribution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
