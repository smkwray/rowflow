"""Retrieve a small, explicitly selected set of dated Federal Reserve tables."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from rowflow.io import sha256_file


def acquire_archive(url: str, vintage: str, members: list[str], output: Path) -> dict:
    """Retain exact selected members and their dictionary files, never the full tree."""
    expected_url = (
        "https://www.federalreserve.gov/releases/z1/"
        f"{vintage.replace('-', '')}/z1_csv_files.zip"
    )
    if url != expected_url:
        raise ValueError("A dated Federal Reserve archive URL matching the vintage is required")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite a source vintage: {output}")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        headers = dict(response.headers)
        resolved_url = response.url
    if resolved_url != url:
        raise ValueError(f"Dated source redirected to {resolved_url}")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        selected = {}
        for member in members:
            if member not in archive.namelist() or ".." in Path(member).parts:
                raise ValueError(f"Invalid or missing archive member: {member}")
            selected[member] = archive.read(member)  # ZipFile verifies the member CRC.
    output.mkdir(parents=True)
    files = []
    for member, content in selected.items():
        path = output / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append({"path": member, "bytes": len(content), "sha256": sha256_file(path)})
    receipt = {
        "vintage": vintage,
        "source_url": url,
        "resolved_url": resolved_url,
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "last_modified": headers.get("Last-Modified"),
        "archive_bytes": len(payload),
        "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "retained_files": files,
        "source_id_convention": "Federal Reserve IDs (FU...Q), not FRED aliases",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def acquire_alfred_series(vintage: str, series: dict[str, str], output: Path) -> dict:
    """Pin explicitly requested quarterly sidecars and verify returned vintage labels."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite source sidecars: {output}")
    records, payloads = [], {}
    for series_id, description in series.items():
        query = urlencode({"id": series_id, "cosd": "2001-10-01", "coed": "2025-12-31", "vintage_date": vintage})
        url = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?" + query
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        header = payload.decode("utf-8-sig").splitlines()[0]
        if header != f"observation_date,{series_id}_{vintage.replace('-', '')}":
            raise ValueError(f"Unexpected ALFRED series/vintage header: {header}")
        filename = series_id + ".csv"
        payloads[filename] = payload
        records.append({"path": filename, "series_id": series_id, "description": description,
                        "source_url": url, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
    output.mkdir(parents=True)
    for filename, payload in payloads.items():
        (output / filename).write_bytes(payload)
    receipt = {"vintage": vintage, "retrieved_utc": datetime.now(UTC).isoformat(), "retained_files": records}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
