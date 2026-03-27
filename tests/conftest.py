import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yetter as yetter_sdk
from yetter.client import yetter as YetterBackend

DEFAULT_ENDPOINT = "https://api.yetter.ai"


def _reset_yetter_state() -> None:
    YetterBackend._api_key = None
    YetterBackend._endpoint = DEFAULT_ENDPOINT
    YetterBackend._cached_client = None
    yetter_sdk._yetter_instance = YetterBackend()


@pytest.fixture(autouse=True)
def reset_yetter_state(monkeypatch):
    monkeypatch.delenv("YTR_API_KEY", raising=False)
    _reset_yetter_state()
    yield
    _reset_yetter_state()


@pytest.fixture
def run_async():
    def _run(coro):
        return asyncio.run(coro)

    return _run


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run live API integration tests",
    )
    parser.addoption(
        "--timing-report",
        action="store",
        default=None,
        help="write Yetter timing results to a JSON file",
    )


def pytest_configure(config):
    config._yetter_timing_records = []


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(
        reason="integration tests require --run-integration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    records = getattr(config, "_yetter_timing_records", [])
    if not records:
        return

    terminalreporter.section("Yetter timing report")
    for record in records:
        name = record["name"]
        elapsed = record["elapsed_seconds"]
        metadata = record.get("metadata") or {}
        metadata_text = (
            " ".join(
                f"{key}={json.dumps(value)}" if isinstance(value, list) else f"{key}={value}"
                for key, value in metadata.items()
            )
            if metadata
            else ""
        )
        terminalreporter.write_line(
            f"{name}: {elapsed:.3f}s".rstrip()
            + (f" {metadata_text}" if metadata_text else "")
        )

    output_path = config.getoption("--timing-report")
    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(records, indent=2), encoding="utf-8")
        terminalreporter.write_line(f"saved timing report to {target}")


@pytest.fixture
def timing_recorder(request):
    records = request.config._yetter_timing_records

    def _record(name, elapsed_seconds, **metadata):
        records.append(
            {
                "name": name,
                "elapsed_seconds": elapsed_seconds,
                "metadata": metadata or None,
            }
        )

    return _record
