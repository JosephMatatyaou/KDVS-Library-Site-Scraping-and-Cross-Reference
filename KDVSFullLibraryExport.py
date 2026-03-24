#!/usr/bin/env python3
"""Export the full KDVS library album catalog via the site login + API.

Example:
    python3 KDVSFullLibraryExport.py

If username or password are omitted, the script prompts for them securely.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from getpass import getpass
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urljoin

import requests


BASE_URL = "https://library.kdvs.org"
LOGIN_URL = f"{BASE_URL}/login/?next=/"
LOGIN_POST_URL = f"{BASE_URL}/login/"
ALBUMS_URL = f"{BASE_URL}/library/albums/"
API_ALBUMS_URL = f"{BASE_URL}/api/library/albums/"
DEFAULT_PAGE_SIZE = 250
DEFAULT_TIMEOUT = 120
DEFAULT_PAUSE_SECONDS = 0.05
DEFAULT_REQUEST_RETRIES = 5
DEFAULT_RETRY_BACKOFF = 2.0
USER_AGENT = "KDVSFullLibraryExport/1.0"
OUTPUT_SUFFIXES = {
    "csv": ".csv",
    "json": ".json",
    "jsonl": ".jsonl",
}

PREFERRED_FIELD_ORDER = [
    "pk",
    "title",
    "artists_joined",
    "artists_count",
    "labels_count",
    "genre",
    "release_date",
    "tracking_end_date",
    "promoter",
    "format_name",
    "format_id",
    "format",
    "adder",
    "created",
    "modified",
    "api_url",
    "artists",
    "labels",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log into the KDVS library site, page through the album API, and export the full catalog.",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("KDVS_USERNAME"),
        help="KDVS site username. Falls back to KDVS_USERNAME, then prompts if still missing.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("KDVS_PASSWORD"),
        help="KDVS site password. Falls back to KDVS_PASSWORD, then prompts if still missing.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path. If omitted, a timestamped filename is created in the current directory.",
    )
    parser.add_argument(
        "--format",
        choices=sorted(OUTPUT_SUFFIXES),
        default="csv",
        help="Export format. Defaults to csv.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Requested API page size. Defaults to {DEFAULT_PAGE_SIZE}.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=DEFAULT_PAUSE_SECONDS,
        help=(
            "Delay between page requests so the export stays polite to the KDVS server. "
            f"Defaults to {DEFAULT_PAUSE_SECONDS}."
        ),
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds. Defaults to {DEFAULT_TIMEOUT}.",
    )
    parser.add_argument(
        "--request-retries",
        type=int,
        default=DEFAULT_REQUEST_RETRIES,
        help=f"How many times to retry a failed request. Defaults to {DEFAULT_REQUEST_RETRIES}.",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF,
        help=f"Base seconds for exponential retry backoff. Defaults to {DEFAULT_RETRY_BACKOFF}.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Optional testing limit for the number of API pages to fetch.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional testing limit for the number of album records to export.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra progress information while exporting.",
    )
    parser.add_argument(
        "--fresh-start",
        action="store_true",
        help="Delete any partial export state for this output file and start over from page 1.",
    )
    return parser.parse_args()


def print_status(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def prompt_for_username(username: str | None) -> str:
    resolved_username = (username or "").strip()
    while not resolved_username:
        resolved_username = input("KDVS username: ").strip()
    return resolved_username


def prompt_for_password(password: str | None) -> str:
    resolved_password = password or ""
    while not resolved_password:
        resolved_password = getpass("KDVS password: ")
    return resolved_password


def initial_api_url(page_size: int) -> str:
    return f"{API_ALBUMS_URL}?limit={page_size}"


def partial_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.partial.jsonl")


def state_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.state.json")


def remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def record_identifier(record: dict[str, Any]) -> str:
    for key in ("pk", "api_url", "url"):
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def iter_partial_records(partial_path: Path):
    if not partial_path.exists():
        return

    with partial_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            yield json.loads(stripped_line)


def load_seen_record_ids(partial_path: Path) -> set[str]:
    seen_ids: set[str] = set()
    for record in iter_partial_records(partial_path) or []:
        record_id = record_identifier(record)
        if record_id:
            seen_ids.add(record_id)
    return seen_ids


def save_export_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_export_state(state_path: Path) -> dict[str, Any]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def request_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    context: str,
    timeout: float,
    retries: int,
    retry_backoff: float,
    **kwargs: Any,
) -> requests.Response:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in {408, 429} or response.status_code >= 500:
                response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break

            sleep_seconds = retry_backoff * (2 ** attempt)
            print_status(
                f"{context} failed ({exc}). Retrying in {sleep_seconds:.1f}s "
                f"({attempt + 1}/{retries})..."
            )
            time.sleep(sleep_seconds)

    assert last_error is not None
    raise last_error


def extract_csrf_token(html: str) -> str:
    patterns = [
        r"name='csrfmiddlewaretoken' value='([^']+)'",
        r'name="csrfmiddlewaretoken" value="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    raise RuntimeError("Could not find the KDVS login CSRF token.")


def parse_json_response(response: requests.Response, context: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        snippet = " ".join(response.text.split())[:240]
        raise RuntimeError(f"{context} did not return JSON. Response started with: {snippet}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{context} returned an unexpected JSON payload.")

    return payload


def login_to_kdvs(
    session: requests.Session,
    username: str,
    password: str,
    *,
    request_timeout: float,
    request_retries: int,
    retry_backoff: float,
) -> None:
    login_page = request_with_retries(
        session,
        "GET",
        LOGIN_URL,
        context="KDVS login page",
        timeout=request_timeout,
        retries=request_retries,
        retry_backoff=retry_backoff,
    )
    login_page.raise_for_status()
    csrf_token = extract_csrf_token(login_page.text)

    response = request_with_retries(
        session,
        "POST",
        LOGIN_POST_URL,
        context="KDVS login submission",
        timeout=request_timeout,
        retries=request_retries,
        retry_backoff=retry_backoff,
        data={
            "csrfmiddlewaretoken": csrf_token,
            "username": username,
            "password": password,
            "next": "/",
        },
        headers={"Referer": LOGIN_URL},
    )
    response.raise_for_status()

    albums_page = request_with_retries(
        session,
        "GET",
        ALBUMS_URL,
        context="KDVS albums page after login",
        timeout=request_timeout,
        retries=request_retries,
        retry_backoff=retry_backoff,
    )
    albums_page.raise_for_status()

    if "Logout" not in albums_page.text and "/logout" not in albums_page.text:
        raise RuntimeError("KDVS login failed. Please check your username and password.")


def clean_string(value: str) -> str:
    return value.strip()


def clean_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return clean_string(value)
    return value


def flatten_record(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat_record: dict[str, Any] = {}

    for key, value in record.items():
        field_name = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            nested = flatten_record(value, field_name)
            if nested:
                flat_record.update(nested)
            else:
                flat_record[field_name] = "{}"
            continue

        if isinstance(value, list):
            cleaned_items = [clean_scalar(item) if not isinstance(item, (dict, list)) else item for item in value]
            flat_record[field_name] = json.dumps(cleaned_items, ensure_ascii=False)
            continue

        flat_record[field_name] = clean_scalar(value)

    return flat_record


def join_list_items(value: Any) -> str:
    if not isinstance(value, list):
        return ""

    cleaned_items = [str(clean_scalar(item)) for item in value if clean_scalar(item) != ""]
    return " | ".join(cleaned_items)


def extract_related_id(resource_url: str) -> str:
    match = re.search(r"/(\d+)/?$", resource_url.strip())
    return match.group(1) if match else ""


def resolve_related_name(
    session: requests.Session,
    resource_url: str,
    cache: dict[str, str],
    request_timeout: float,
    request_retries: int,
    retry_backoff: float,
    verbose: bool = False,
) -> str:
    if not resource_url:
        return ""

    if resource_url in cache:
        return cache[resource_url]

    try:
        response = request_with_retries(
            session,
            "GET",
            resource_url,
            context=f"Related resource {resource_url}",
            timeout=request_timeout,
            retries=request_retries,
            retry_backoff=retry_backoff,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = parse_json_response(response, f"Related resource {resource_url}")

        for key in ("name", "title", "label", "slug", "pk"):
            value = payload.get(key)
            if value not in (None, ""):
                resolved_name = str(clean_scalar(value))
                cache[resource_url] = resolved_name
                return resolved_name
    except Exception as exc:
        if verbose:
            print_status(f"Could not resolve related resource {resource_url}: {exc}")

    cache[resource_url] = ""
    return ""


def normalize_album_record(
    record: dict[str, Any],
    session: requests.Session,
    format_name_cache: dict[str, str],
    request_timeout: float,
    request_retries: int,
    retry_backoff: float,
    verbose: bool = False,
) -> dict[str, Any]:
    normalized = flatten_record(record)

    api_url = normalized.pop("url", "")
    if api_url:
        normalized["api_url"] = api_url

    artists = record.get("artists")
    if isinstance(artists, list):
        normalized["artists"] = json.dumps([clean_scalar(item) for item in artists], ensure_ascii=False)
        normalized["artists_joined"] = join_list_items(artists)
        normalized["artists_count"] = len([item for item in artists if clean_scalar(item) != ""])

    labels = record.get("labels")
    if isinstance(labels, list):
        normalized["labels"] = json.dumps(labels, ensure_ascii=False)
        normalized["labels_count"] = len([item for item in labels if clean_scalar(item) != ""])

    format_url = record.get("format")
    if isinstance(format_url, str) and format_url.strip():
        normalized["format"] = format_url.strip()
        normalized["format_id"] = extract_related_id(format_url)
        normalized["format_name"] = resolve_related_name(
            session,
            format_url,
            cache=format_name_cache,
            request_timeout=request_timeout,
            request_retries=request_retries,
            retry_backoff=retry_backoff,
            verbose=verbose,
        )

    return normalized


def append_records_to_partial(
    partial_path: Path,
    records: list[dict[str, Any]],
    seen_ids: set[str],
) -> int:
    new_records = 0

    with partial_path.open("a", encoding="utf-8") as handle:
        for record in records:
            record_id = record_identifier(record)
            if record_id and record_id in seen_ids:
                continue

            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
            if record_id:
                seen_ids.add(record_id)
            new_records += 1

    return new_records


def finalize_csv_output(partial_path: Path, output_path: Path) -> None:
    all_fields: set[str] = set()
    seen_ids: set[str] = set()

    for record in iter_partial_records(partial_path) or []:
        record_id = record_identifier(record)
        if record_id and record_id in seen_ids:
            continue
        if record_id:
            seen_ids.add(record_id)
        all_fields.update(record.keys())

    fieldnames = ordered_fieldnames([{field: "" for field in all_fields}]) if all_fields else []

    seen_ids.clear()
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for record in iter_partial_records(partial_path) or []:
            record_id = record_identifier(record)
            if record_id and record_id in seen_ids:
                continue
            if record_id:
                seen_ids.add(record_id)
            writer.writerow(record)


def finalize_jsonl_output(partial_path: Path, output_path: Path) -> None:
    seen_ids: set[str] = set()

    with output_path.open("w", encoding="utf-8") as handle:
        for record in iter_partial_records(partial_path) or []:
            record_id = record_identifier(record)
            if record_id and record_id in seen_ids:
                continue
            if record_id:
                seen_ids.add(record_id)
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def finalize_json_output(partial_path: Path, output_path: Path) -> None:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for record in iter_partial_records(partial_path) or []:
        record_id = record_identifier(record)
        if record_id and record_id in seen_ids:
            continue
        if record_id:
            seen_ids.add(record_id)
        records.append(record)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def finalize_output(partial_path: Path, output_path: Path, output_format: str) -> None:
    if output_format == "csv":
        finalize_csv_output(partial_path, output_path)
        return

    if output_format == "jsonl":
        finalize_jsonl_output(partial_path, output_path)
        return

    if output_format == "json":
        finalize_json_output(partial_path, output_path)
        return

    raise ValueError(f"Unsupported output format: {output_format}")


def fetch_album_records_to_partial(
    session: requests.Session,
    partial_path: Path,
    state_path: Path,
    state: dict[str, Any],
    seen_ids: set[str],
    *,
    pause_seconds: float,
    max_pages: int | None,
    max_records: int | None,
    request_timeout: float,
    request_retries: int,
    retry_backoff: float,
    verbose: bool,
) -> tuple[int | None, int]:
    format_name_cache: dict[str, str] = {}
    next_url = state["next_url"]
    page_number = state["page_number"]
    expected_total = state.get("expected_total")

    while next_url:
        if max_pages is not None and page_number > max_pages:
            break

        if max_records is not None and len(seen_ids) >= max_records:
            break

        response = request_with_retries(
            session,
            "GET",
            next_url,
            context=f"Album API page {page_number}",
            timeout=request_timeout,
            retries=request_retries,
            retry_backoff=retry_backoff,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        payload = parse_json_response(response, f"Album API page {page_number}")
        if expected_total is None and isinstance(payload.get("count"), int):
            expected_total = payload["count"]

        page_results = payload.get("results", [])
        if not isinstance(page_results, list):
            raise RuntimeError(f"Album API page {page_number} returned an unexpected results payload.")

        remaining_records = None
        if max_records is not None:
            remaining_records = max_records - len(seen_ids)
            if remaining_records <= 0:
                break

        normalized_records: list[dict[str, Any]] = []
        for record in page_results:
            if not isinstance(record, dict):
                continue
            normalized_records.append(
                normalize_album_record(
                    record,
                    session=session,
                    format_name_cache=format_name_cache,
                    request_timeout=request_timeout,
                    request_retries=request_retries,
                    retry_backoff=retry_backoff,
                    verbose=verbose,
                )
            )
            if remaining_records is not None and len(normalized_records) >= remaining_records:
                break

        append_records_to_partial(partial_path, normalized_records, seen_ids)

        raw_next_url = payload.get("next")
        next_url = urljoin(response.url, str(raw_next_url)) if raw_next_url else None
        state.update(
            {
                "next_url": next_url,
                "page_number": page_number + 1,
                "expected_total": expected_total,
            }
        )
        save_export_state(state_path, state)

        total_display = expected_total if expected_total is not None else "?"
        print_status(
            f"Fetched page {page_number}: {len(page_results)} albums this page, {len(seen_ids)} total of {total_display}."
        )

        if pause_seconds > 0 and next_url:
            time.sleep(pause_seconds)

        page_number += 1

    return expected_total, len(seen_ids)


def default_output_path(output_format: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = OUTPUT_SUFFIXES[output_format]
    return Path.cwd() / f"kdvs_full_library_{timestamp}{suffix}"


def resolve_output_path(requested_path: Path | None, output_format: str) -> Path:
    if requested_path is None:
        return default_output_path(output_format)

    suffix = OUTPUT_SUFFIXES[output_format]
    if requested_path.suffix:
        return requested_path
    return requested_path.with_suffix(suffix)


def ordered_fieldnames(records: list[dict[str, Any]]) -> list[str]:
    all_fields: set[str] = set()
    for record in records:
        all_fields.update(record.keys())

    ordered: list[str] = []
    for field in PREFERRED_FIELD_ORDER:
        if field in all_fields:
            ordered.append(field)

    for field in sorted(all_fields):
        if field not in ordered:
            ordered.append(field)

    return ordered


def validate_args(args: argparse.Namespace) -> None:
    if args.page_size <= 0:
        raise ValueError("--page-size must be greater than 0.")

    if args.pause_seconds < 0:
        raise ValueError("--pause-seconds cannot be negative.")

    if args.request_timeout <= 0:
        raise ValueError("--request-timeout must be greater than 0.")

    if args.request_retries < 0:
        raise ValueError("--request-retries cannot be negative.")

    if args.retry_backoff < 0:
        raise ValueError("--retry-backoff cannot be negative.")

    if args.max_pages is not None and args.max_pages <= 0:
        raise ValueError("--max-pages must be greater than 0.")

    if args.max_records is not None and args.max_records <= 0:
        raise ValueError("--max-records must be greater than 0.")


def main() -> int:
    args = parse_args()
    username = prompt_for_username(args.username)
    password = prompt_for_password(args.password)

    try:
        validate_args(args)
    except ValueError as exc:
        print_status(f"Argument error: {exc}")
        return 2

    output_path = resolve_output_path(args.output, args.format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = partial_output_path(output_path)
    state_path = state_output_path(output_path)

    if args.fresh_start:
        remove_if_exists(output_path)
        remove_if_exists(partial_path)
        remove_if_exists(state_path)

    if state_path.exists() and partial_path.exists():
        state = load_export_state(state_path)
        if state.get("output_format") != args.format:
            print_status("Existing resume state uses a different output format. Re-run with --fresh-start.")
            return 2
        print_status(
            f"Resuming export from page {state.get('page_number', '?')} using {partial_path.name}..."
        )
    else:
        if state_path.exists() or partial_path.exists():
            print_status(
                "Found partial export files without a complete resume state. "
                "Re-run with --fresh-start to restart cleanly."
            )
            return 2
        if output_path.exists():
            print_status(
                f"{output_path.name} already exists. Use --fresh-start to overwrite it or choose a new --output."
            )
            return 2

        state = {
            "output_format": args.format,
            "next_url": initial_api_url(args.page_size),
            "page_number": 1,
            "expected_total": None,
        }
        save_export_state(state_path, state)

    seen_ids = load_seen_record_ids(partial_path)
    if seen_ids:
        print_status(f"Loaded {len(seen_ids)} already-saved albums from {partial_path.name}.")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        print_status(f"Logging into KDVS as {username}...")
        login_to_kdvs(
            session,
            username,
            password,
            request_timeout=args.request_timeout,
            request_retries=args.request_retries,
            retry_backoff=args.retry_backoff,
        )

        print_status("Starting API export...")
        expected_total, saved_records = fetch_album_records_to_partial(
            session,
            partial_path,
            state_path,
            state,
            pause_seconds=args.pause_seconds,
            max_pages=args.max_pages,
            max_records=args.max_records,
            seen_ids=seen_ids,
            request_timeout=args.request_timeout,
            request_retries=args.request_retries,
            retry_backoff=args.retry_backoff,
            verbose=args.verbose,
        )

        print_status(f"Finalizing {args.format} output...")
        finalize_output(partial_path, output_path, args.format)
        remove_if_exists(partial_path)
        remove_if_exists(state_path)
    except requests.RequestException as exc:
        print_status(
            f"Network error while exporting KDVS library: {exc}\n"
            f"Partial progress is saved in {partial_path.name}. "
            "Run the same command again to resume, or add --fresh-start to restart."
        )
        return 1
    except KeyboardInterrupt:
        print_status(
            f"Export cancelled by user.\nPartial progress is saved in {partial_path.name}. "
            "Run the same command again to resume."
        )
        return 130
    except Exception as exc:
        print_status(
            f"Export failed: {exc}\nPartial progress is saved in {partial_path.name}. "
            "Run the same command again to resume, or add --fresh-start to restart."
        )
        return 1
    finally:
        session.close()

    expected_text = expected_total if expected_total is not None else "unknown"
    print_status(
        f"Export complete. Saved {saved_records} albums to {output_path} "
        f"(API reported {expected_text} total albums)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
