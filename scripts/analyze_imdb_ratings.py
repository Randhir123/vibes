#!/usr/bin/env python3
"""Download IMDb datasets and analyze movie rating distribution."""

from __future__ import annotations

import argparse
import csv
import gzip
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable
from urllib.error import URLError
from urllib.request import urlopen

DATASET_URLS: Dict[str, str] = {
    "title.basics.tsv.gz": "https://datasets.imdbws.com/title.basics.tsv.gz",
    "title.ratings.tsv.gz": "https://datasets.imdbws.com/title.ratings.tsv.gz",
}


def download_file(url: str, destination: Path) -> None:
    """Download *url* to *destination* unless the file already exists."""
    if destination.exists():
        print(f"Skipping download of {url}; file already exists at {destination}.")
        return

    print(f"Downloading {url} -> {destination}")
    try:
        with urlopen(url) as response, open(destination, "wb") as output_file:
            shutil.copyfileobj(response, output_file)
    except URLError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def load_movie_ids(basics_path: Path) -> set[str]:
    """Return the set of IMDb title identifiers that correspond to movies."""
    movie_ids: set[str] = set()
    with gzip.open(basics_path, "rt", encoding="utf-8") as basics_file:
        reader = csv.DictReader(basics_file, delimiter="\t")
        for row in reader:
            if row.get("titleType") == "movie":
                movie_ids.add(row["tconst"])
    return movie_ids


def iter_ratings(ratings_path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(ratings_path, "rt", encoding="utf-8") as ratings_file:
        yield from csv.DictReader(ratings_file, delimiter="\t")


def compute_distribution(movie_ids: set[str], ratings_path: Path) -> dict[str, object]:
    rating_bucket_counts = Counter({i: 0 for i in range(0, 11)})
    rating_bucket_votes = Counter({i: 0 for i in range(0, 11)})
    average_rating_counts: Counter[float] = Counter()

    total_movies = 0
    total_votes = 0
    rating_sum = 0.0
    rating_sq_sum = 0.0
    min_rating = math.inf
    max_rating = -math.inf

    for row in iter_ratings(ratings_path):
        tconst = row["tconst"]
        if tconst not in movie_ids:
            continue

        rating = float(row["averageRating"])
        votes = int(row["numVotes"])

        total_movies += 1
        total_votes += votes
        rating_sum += rating
        rating_sq_sum += rating * rating
        min_rating = min(min_rating, rating)
        max_rating = max(max_rating, rating)

        bucket = int(round(rating))
        bucket = min(max(bucket, 0), 10)
        rating_bucket_counts[bucket] += 1
        rating_bucket_votes[bucket] += votes

        average_rating_counts[rating] += 1

    if total_movies == 0:
        raise RuntimeError("No movie ratings found in the dataset.")

    mean_rating = rating_sum / total_movies
    variance = (rating_sq_sum / total_movies) - (mean_rating ** 2)
    std_dev = math.sqrt(max(variance, 0.0))

    # Compute median from the histogram of average ratings.
    sorted_ratings = sorted(average_rating_counts.items())
    if total_movies % 2 == 1:
        target_indices = [total_movies // 2]
    else:
        target_indices = [total_movies // 2 - 1, total_movies // 2]

    median_hits = []
    cumulative = 0
    for value, count in sorted_ratings:
        previous = cumulative
        cumulative += count
        for target in target_indices:
            if previous <= target < cumulative:
                median_hits.append(value)
        if len(median_hits) == len(target_indices):
            break

    if not median_hits:
        median = float("nan")
    else:
        median = sum(median_hits) / len(median_hits)

    distribution_rows = []
    for bucket in range(0, 11):
        movie_count = rating_bucket_counts[bucket]
        vote_count = rating_bucket_votes[bucket]
        distribution_rows.append(
            {
                "rating_bucket": bucket,
                "movie_count": movie_count,
                "share_of_movies": movie_count / total_movies,
                "total_votes": vote_count,
                "share_of_votes": vote_count / total_votes if total_votes else 0.0,
            }
        )

    summary = {
        "total_movies": total_movies,
        "total_votes": total_votes,
        "mean": mean_rating,
        "median": median,
        "std": std_dev,
        "min": min_rating,
        "max": max_rating,
        "distribution": distribution_rows,
    }

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/imdb"),
        help="Directory where IMDb datasets will be stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in DATASET_URLS.items():
        download_file(url, data_dir / filename)

    basics_path = data_dir / "title.basics.tsv.gz"
    ratings_path = data_dir / "title.ratings.tsv.gz"

    movie_ids = load_movie_ids(basics_path)
    summary = compute_distribution(movie_ids, ratings_path)

    print(
        "Loaded {total_movies:,} movie rating records with {total_votes:,} total votes.".format(
            total_movies=summary["total_movies"], total_votes=summary["total_votes"]
        )
    )

    print("\nDistribution of movies by rounded IMDb user rating:")
    print(
        "rating  movie_count  share_of_movies  total_votes  share_of_votes"
    )
    for row in summary["distribution"]:
        print(
            f"{row['rating_bucket']:>6}  {row['movie_count']:>11}  {row['share_of_movies']:.2%:>16}"
            f"  {row['total_votes']:>11}  {row['share_of_votes']:.2%:>15}"
        )

    print("\nSummary of average ratings across movies:")
    print(f"    mean: {summary['mean']:.2f}")
    print(f"  median: {summary['median']:.2f}")
    print(f"     std: {summary['std']:.2f}")
    print(f"     min: {summary['min']:.2f}")
    print(f"     max: {summary['max']:.2f}")


if __name__ == "__main__":
    main()
