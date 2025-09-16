# vibes

Vibe coding

## IMDb rating distribution analysis

The `scripts/analyze_imdb_ratings.py` helper downloads the official IMDb
TSV dumps from [datasets.imdbws.com](https://datasets.imdbws.com/) and
prints the distribution of average ratings for feature films. Because
these files are large (several hundred megabytes) and updated daily, the
script saves them inside a local `data/` directory that is excluded from
version control.

Run the script with Python 3.11 or newer:

```bash
python scripts/analyze_imdb_ratings.py
```

Use the `--force-download` flag if you want to refresh the cached data.
