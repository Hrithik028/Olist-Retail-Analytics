"""Create source-preserving Bronze CSVs with ingestion metadata."""

from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "data" / "raw"
DESTINATION_PATH = PROJECT_ROOT / "data" / "bronze"
LOAD_MARKER_PATH = PROJECT_ROOT / "data" / "latest_load_date.txt"


def read_last_load_date() -> datetime:
    """Return the previous successful load time, or the earliest date."""
    if not LOAD_MARKER_PATH.exists():
        return datetime.min

    date_str = LOAD_MARKER_PATH.read_text(encoding="utf-8").strip()
    return datetime.fromisoformat(date_str) if date_str else datetime.min


def main() -> None:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Source directory not found: {SOURCE_PATH}. See data/README.md."
        )

    DESTINATION_PATH.mkdir(parents=True, exist_ok=True)
    current_date = read_last_load_date()
    load_date = datetime.now()
    print(f"Latest load date: {current_date}")

    for file_path in sorted(SOURCE_PATH.glob("*.csv")):
        print(f"Working on: {file_path.name}")
        modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)

        if modified_at <= current_date:
            print(f"{file_path.name}: no changes detected\n")
            continue

        dataframe = pd.read_csv(file_path)
        dataframe["load_date"] = load_date
        dataframe["file_name"] = file_path.stem

        output_path = DESTINATION_PATH / f"{file_path.stem}_bronze.csv"
        dataframe.to_csv(output_path, index=False)
        print(f"{output_path.name} created successfully\n")

    LOAD_MARKER_PATH.write_text(load_date.isoformat(sep=" "), encoding="utf-8")
    print("Latest load date stored successfully")


if __name__ == "__main__":
    main()
