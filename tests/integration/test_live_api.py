import base64
import json
import os
import time

import pytest

import yetter

pytestmark = pytest.mark.integration

DEFAULT_T2I_MODEL = "ytr-ai/z_image/turbo/t2i"
DEFAULT_I2I_MODEL = "ytr-ai/qwen/image-edit/i2i"
LIVE_BENCHMARK_RUNS = 5
LIVE_BENCHMARK_WARMUP_RUNS = 1
TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+L0foAAAAASUVORK5CYII="
)


def _base_live_settings():
    api_key = os.environ.get("YTR_LIVE_API_KEY") or os.environ.get("YTR_API_KEY")
    endpoint = os.environ.get("YTR_LIVE_ENDPOINT")

    if not api_key:
        pytest.skip("set YTR_LIVE_API_KEY or YTR_API_KEY to run live integration tests")

    return {
        "api_key": api_key,
        "endpoint": endpoint,
    }


def _t2i_settings():
    settings = _base_live_settings()
    settings.update(
        {
            "model": os.environ.get("YTR_LIVE_T2I_MODEL", DEFAULT_T2I_MODEL),
            "prompt": os.environ.get(
                "YTR_LIVE_T2I_PROMPT",
                "A minimal studio product photo of a glass cube on a white background",
            ),
        }
    )
    return settings


def _i2i_settings():
    settings = _base_live_settings()
    extra_input = os.environ.get("YTR_LIVE_I2I_EXTRA_INPUT_JSON")
    settings.update(
        {
            "model": os.environ.get("YTR_LIVE_I2I_MODEL", DEFAULT_I2I_MODEL),
            "prompt": os.environ.get(
                "YTR_LIVE_I2I_PROMPT",
                "Make this image more vibrant with enhanced colors and dramatic lighting",
            ),
            "extra_input": json.loads(extra_input) if extra_input else {},
        }
    )
    return settings


def _configure_client(settings):
    yetter.configure(
        api_key=settings["api_key"],
        api_endpoint=settings["endpoint"],
    )


def _endpoint_label(settings):
    return settings["endpoint"] or "default"


def _build_image_edit_args(settings, image_url):
    shared_input = {
        "prompt": settings["prompt"],
        "image_url": [image_url],
        "image_size": "auto",
        "num_images": 1,
        "enable_safety_checker": False,
        **settings["extra_input"],
    }
    return {
        **shared_input,
        "input": shared_input.copy(),
    }


def _record_live_timing(timing_recorder, name, elapsed, settings, **metadata):
    timing_recorder(
        name,
        elapsed,
        model=settings["model"],
        endpoint=_endpoint_label(settings),
        **metadata,
    )


def _average_excluding_warmup(samples):
    measured_samples = samples[LIVE_BENCHMARK_WARMUP_RUNS:]
    return sum(measured_samples) / len(measured_samples)


def _benchmark_metadata(samples, **extra_metadata):
    return {
        "runs": len(samples),
        "warmup_runs_discarded": LIVE_BENCHMARK_WARMUP_RUNS,
        "measured_runs": len(samples) - LIVE_BENCHMARK_WARMUP_RUNS,
        "warmup_seconds": round(samples[0], 3),
        "samples_seconds": [round(sample, 3) for sample in samples],
        **extra_metadata,
    }


def test_live_text_to_image_reports_wall_clock_time(run_async, timing_recorder):
    settings = _t2i_settings()
    _configure_client(settings)

    async def scenario():
        result = None
        samples = []
        for _ in range(LIVE_BENCHMARK_RUNS):
            started = time.perf_counter()
            result = await yetter.run(
                settings["model"],
                {"prompt": settings["prompt"]},
            )
            samples.append(time.perf_counter() - started)
        return result, samples

    result, samples = run_async(scenario())
    average_elapsed = _average_excluding_warmup(samples)
    _record_live_timing(
        timing_recorder,
        "live_text_to_image",
        average_elapsed,
        settings,
        **_benchmark_metadata(samples),
    )

    assert average_elapsed >= 0
    assert isinstance(result, dict)
    assert result


def test_live_upload_and_image_edit_report_wall_clock_time(
    run_async,
    timing_recorder,
    tmp_path,
):
    settings = _i2i_settings()
    _configure_client(settings)

    image_path = tmp_path / "live-input.png"
    image_path.write_bytes(base64.b64decode(TINY_PNG_BASE64))

    async def scenario():
        upload_result = None
        result = None
        upload_samples = []
        edit_samples = []
        for _ in range(LIVE_BENCHMARK_RUNS):
            upload_started = time.perf_counter()
            upload_result = await yetter.upload_file(str(image_path))
            upload_samples.append(time.perf_counter() - upload_started)

            args = _build_image_edit_args(settings, upload_result.url)
            edit_started = time.perf_counter()
            result = await yetter.run(settings["model"], args)
            edit_samples.append(time.perf_counter() - edit_started)
        return upload_result, upload_samples, result, edit_samples

    upload_result, upload_samples, result, edit_samples = run_async(scenario())
    average_upload_elapsed = _average_excluding_warmup(upload_samples)
    average_edit_elapsed = _average_excluding_warmup(edit_samples)

    _record_live_timing(
        timing_recorder,
        "live_upload",
        average_upload_elapsed,
        settings,
        **_benchmark_metadata(upload_samples),
    )
    _record_live_timing(
        timing_recorder,
        "live_image_edit",
        average_edit_elapsed,
        settings,
        **_benchmark_metadata(edit_samples),
        image_input_key="image_url",
    )

    assert average_upload_elapsed >= 0
    assert average_edit_elapsed >= 0
    assert upload_result.url
    assert isinstance(result, dict)
    assert result
