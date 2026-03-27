# AGENTS.md

This document is based only on git-tracked files in this repository. Ignore local untracked files when analyzing, editing, or validating changes. Do not add API keys, bearer tokens, uploaded assets, or generated JSON artifacts to the repository.

## Repository Purpose

This repository contains the `yetter` Python client, a lightweight async SDK for the Yetter image generation API.

The tracked code currently supports four main workflows:

- One-shot generation through `yetter.run(...)`
- Polling-based completion through `yetter.subscribe(...)`
- Server-sent events streaming through `yetter.stream(...)`
- File upload through presigned URLs via `yetter.upload_file(...)`

The package targets Python 3.8+ and uses `httpx` for async HTTP access and `pydantic` for request/response models.

## Repository Structure

- `README.md`: Public usage guide, installation notes, and example snippets.
- `pyproject.toml`: Packaging metadata, runtime dependencies, and dynamic versioning through `setuptools_scm`.
- `requirements.txt`: Runtime dependency pins used for local installation.
- `src/yetter/__init__.py`: Public package surface and top-level async helpers.
- `src/yetter/api.py`: Low-level async API client that performs authenticated HTTP requests.
- `src/yetter/client.py`: High-level workflow logic for run, subscribe, stream, queue helpers, and uploads.
- `src/yetter/types.py`: Pydantic models for API inputs and outputs.
- `examples/run.py`: Minimal one-shot example.
- `examples/subscribe.py`: Polling example with queue updates.
- `tests/conftest.py`: Shared pytest bootstrap and global client state reset.
- `tests/test_public_api.py`: Top-level API guard and delegation coverage.
- `tests/test_api_client.py`: Low-level client request construction and validation coverage.
- `tests/test_subscribe.py`: Polling success, error, and timeout behavior.
- `tests/test_stream.py`: Stream behavior for already-completed requests.
- `tests/test_stream_events.py`: Event parsing and stream lifecycle behavior.
- `tests/test_uploads.py`: Upload orchestration coverage.
- `tests/integration/test_live_api.py`: Opt-in live API smoke test with wall clock timing capture.

## Architecture And Working Style

The package is intentionally small and centers around a module-level singleton client exposed through `yetter`.

Important implementation patterns:

- Configuration is global. `configure(...)` stores the API key and endpoint for later calls.
- Authentication expects a raw API key from callers. The client adds the `Key ` prefix internally.
- `run(...)` is a convenience wrapper that delegates to the streaming flow and waits for the final response.
- `subscribe(...)` uses short polling against the status URL until the request reaches a terminal state.
- `stream(...)` creates a `YetterStream` wrapper that consumes SSE events and resolves the final response on completion.
- `upload_file(...)` requests a presigned upload URL, performs either single-part or multipart upload, and then calls the completion endpoint.
- Data contracts are centralized in `src/yetter/types.py`; behavior changes should keep these models aligned with the API payloads.

When changing code in this repository:

- Preserve the async-first design unless there is a clear product requirement to change it.
- Keep the public entrypoints in `src/yetter/__init__.py` and the README examples in sync.
- Prefer small, explicit changes because the package surface area is narrow and user-facing.
- Do not hardcode credentials or real account data. Use placeholders such as `YOUR_API_KEY` or the `YTR_API_KEY` environment variable in documentation.
- Be careful with auth handling: current code rejects keys that already include `Bearer` or `Key`.
- Keep upload, polling, and streaming timeout/error behavior explicit and easy to trace.

## Development Workflow

The tracked files do not define a full dev-tooling stack such as lint, format, or CI configuration. Work from the package layout directly.

TDD is required for repository changes. Prefer a red-green-refactor workflow: write or update a failing test first, implement the smallest code change that makes it pass, and then clean up the implementation while keeping the test suite green.

Recommended workflow for contributors and agents:

1. Create an isolated Python environment.
2. Install the package from the repository for local development.
3. Add or update tests under `tests/` before changing production code whenever feasible.
4. Make changes in `src/yetter/`.
5. Update `README.md` and `examples/` when public behavior or usage changes.
6. Run targeted validation for the affected flow and keep the test suite passing.

Notes:

- Versioning is derived from git tags that match `v*` through `setuptools_scm`.
- The default API endpoint in tracked code is `https://api.yetter.ai`.
- Public examples assume the user provides credentials at runtime; they should remain free of real secrets.

## Testing And Validation

### Current State

The repository now includes a small pytest-based unit test suite focused on the public client flows and request construction. There is still no tracked CI workflow or lint configuration in the repository at the time of writing.

Run the automated tests with:

1. `pip install -e ".[dev]"`
2. `pytest`

Alternative `uv` workflow:

1. `uv run --extra dev pytest -q`
2. `uv run --extra dev pytest -q --run-integration tests/integration/test_live_api.py --timing-report timing-reports/live-api.json`

Live integration notes:

- The integration test is skipped unless `--run-integration` is provided.
- Real API execution requires either `YTR_LIVE_API_KEY` or `YTR_API_KEY`.
- The default live text-to-image model is `ytr-ai/z_image/turbo/t2i`.
- The default live upload-plus-edit model is `ytr-ai/qwen/image-edit/i2i`.
- The live image-edit payload uses `input.prompt`, `input.image_url`, `input.image_size`, `input.num_images`, and `input.enable_safety_checker`.
- Live timing benchmarks run 5 times, discard the first request as warmup, and report the average of the remaining 4 runs.
- Optional overrides include `YTR_LIVE_ENDPOINT`, `YTR_LIVE_T2I_MODEL`, `YTR_LIVE_T2I_PROMPT`, `YTR_LIVE_I2I_MODEL`, `YTR_LIVE_I2I_PROMPT`, and `YTR_LIVE_I2I_EXTRA_INPUT_JSON`.
- Wall clock results are printed in the pytest terminal summary and can also be written as JSON through `--timing-report`.

### Manual Test Cases

Use placeholder credentials in code and provide the real API key only through the environment or local runtime configuration.

1. Configuration
   - Verify `yetter.configure(api_key="...")` accepts a raw key.
   - Verify keys that already include `Key` or `Bearer` raise `ValueError`.
   - Verify `YTR_API_KEY` is picked up by the default singleton path.

2. One-shot run
   - Call `yetter.run(model, args=...)` with a valid model and prompt.
   - Confirm the call returns the final JSON payload after completion.

3. Polling subscription
   - Call `yetter.subscribe(...)` with `on_queue_update`.
   - Confirm queue or status updates are received during execution.
   - Confirm terminal `ERROR` states surface a useful exception message.
   - Confirm timeout handling raises `TimeoutError` and attempts cancellation.

4. SSE streaming
   - Call `stream = await yetter.stream(...)`.
   - Confirm async iteration yields `GetStatusResponse` updates.
   - Confirm `await stream.done()` returns the final response.
   - Confirm malformed or unexpected SSE data paths fail loudly rather than silently.

5. Upload flow
   - Verify a missing file path raises `FileNotFoundError`.
   - Verify small files complete through single-part upload.
   - Verify multipart uploads sort parts by `part_number` and report progress.
   - Confirm the final response is parsed into `UploadCompleteResponse`.

6. Packaging and imports
   - Verify the package installs from the repository.
   - Verify `import yetter` exposes the documented public helpers and types.
   - Verify the README examples still match the current callable signatures.

## Practical Guidance For Future Changes

- If you change request or response schemas, update `src/yetter/types.py` first and then reconcile the call sites.
- If you change behavior in `run`, `subscribe`, `stream`, or `upload_file`, update both `README.md` and the relevant example scripts.
- Follow TDD by default: start with a failing or missing test, then implement the production change, then refactor safely.
- Extend the pytest suite under `tests/` whenever public behavior changes.
- Do not merge behavior changes without automated test coverage unless the change is documentation-only or a test cannot be written yet; if coverage is deferred, call that out explicitly.
- Keep documentation examples short and safe for copy-paste. Never embed live credentials, signed URLs, or internal-only endpoints.
