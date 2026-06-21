<<<<<<< HEAD
this is 0.5GB, "C:\Users\Hello\Downloads\OmicsSomaticMutations.csv"
read in 200 rows at a time and if OncogeneHighImpact or	TumorSuppressorHighImpact is true


until you get to 1000 rows
=======
#!/usr/bin/env python3
"""Filter a large DepMap mutation CSV in chunks.

Scans the source file 200 rows at a time, keeps rows where either
OncogeneHighImpact or TumorSuppressorHighImpact is true, and stops after
collecting 1000 matching rows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path(r"C:\Users\Hello\Downloads\OmicsSomaticMutations.csv")
DEFAULT_OUTPUT = Path("filtered_depmap_mutations.csv")
CHUNK_SIZE = 200
MAX_ROWS = 1000


def as_bool(series: pd.Series) -> pd.Series:
	"""Normalize common truthy representations to booleans."""
	if series.dtype == bool:
		return series.fillna(False)
	normalized = series.astype(str).str.strip().str.lower()
	return normalized.isin({"true", "1", "yes", "y", "t"})


def filter_depmap(input_path: Path, output_path: Path, max_rows: int = MAX_ROWS) -> int:
	"""Write up to max_rows rows matching the impact flags to output_path."""
	if not input_path.exists():
		raise FileNotFoundError(f"Input file not found: {input_path}")

	header = pd.read_csv(input_path, nrows=0)
	required = {"OncogeneHighImpact", "TumorSuppressorHighImpact"}
	missing = required.difference(header.columns)
	if missing:
		missing_cols = ", ".join(sorted(missing))
		raise ValueError(f"Missing required columns: {missing_cols}")

	kept_chunks: list[pd.DataFrame] = []
	kept_rows = 0

	for chunk in pd.read_csv(input_path, chunksize=CHUNK_SIZE, low_memory=False):
		mask = as_bool(chunk["OncogeneHighImpact"]) | as_bool(chunk["TumorSuppressorHighImpact"])
		if not mask.any():
			continue

		filtered = chunk.loc[mask]
		remaining = max_rows - kept_rows
		if remaining <= 0:
			break

		if len(filtered) > remaining:
			filtered = filtered.head(remaining)

		kept_chunks.append(filtered)
		kept_rows += len(filtered)

		if kept_rows >= max_rows:
			break

	result = pd.concat(kept_chunks, ignore_index=True) if kept_chunks else pd.DataFrame(columns=header.columns)
	result.to_csv(output_path, index=False)
	return len(result)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to OmicsSomaticMutations.csv")
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to write the filtered CSV")
	parser.add_argument("--max-rows", type=int, default=MAX_ROWS, help="Maximum number of matching rows to write")
	args = parser.parse_args()

	written = filter_depmap(args.input, args.output, max_rows=args.max_rows)
	print(f"Wrote {written} rows to {args.output}")


if __name__ == "__main__":
	main()
>>>>>>> main
