# Config Paths

Where paths are hardcoded, and what to edit for the two scenarios below.

## 1. Using an external corpora directory (not `./corpora`)

| File | Variable / arg | Current value | Notes |
|---|---|---|---|
| [utils.py:13](utils.py#L13) | `DEFAULT_CORPORA_DIR` | `str(Path(__file__).resolve().parent.parent / "corpora")` (i.e. the repo-root `corpora/` folder) | Used by `build_indexes` and `search` (via `depsearch.py`) whenever `--base-dir` isn't passed on the CLI. Self-locating via `__file__` (like `TEMP_VOLUME_PATH`), so it resolves to the root `corpora/` folder regardless of process cwd. |
| [../depsearch_interface.py:14](../depsearch_interface.py#L14) | `CORPORA_DIR` | `str(Path(__file__).resolve().parent / "corpora")` (i.e. the repo-root `corpora/` folder) | Used by `get_allowed_corpora()`/`validate_corpus()` to list/validate corpus names for the web API. **Must point at the same directory as `DEFAULT_CORPORA_DIR`** — the API validates against this path, then invokes `depsearch.py` as a subprocess without `--base-dir`, so that subprocess falls back to `utils.DEFAULT_CORPORA_DIR`. If these two diverge, valid corpora will 400 or search will silently look in the wrong place. |
| [../operations.py:24](../operations.py#L24) | `DEFAULT_CORPORA_DIR` | `Path(__file__).resolve().parent / "corpora"` (i.e. the repo-root `corpora/` folder) | **A third independent copy**, used as the fallback default in `get_context()` when a search's `base_dir.pkl` (written into the temp volume by `utils._make_temp_volume`) isn't found. In normal operation `base_dir.pkl` always exists and overrides this, but keep it pointing at the same corpora dir as the other two in case that lookup ever fails. |

Two ways to point at an external directory:
- Change all three constants above to the absolute/relative path of the external directory, **or**
- Leave the constants alone and always pass `--base-dir /path/to/external/corpora` to `depsearch.py` on the CLI (this only covers direct CLI use, not the FastAPI endpoints in `depsearch_interface.py`, which don't forward a `--base-dir`).

Related (only matter if you invoke korpsearch scripts directly instead of through `depsearch.py`):
- [korpsearch/build_indexes.py:145](../korpsearch/build_indexes.py#L145) — `--base-dir` default `Path('corpora')`
- [korpsearch/search_cmdline.py:109](../korpsearch/search_cmdline.py#L109) — `--base-dir` default `Path('corpora')`
- [korpsearch/search_fastapi.py:22](../korpsearch/search_fastapi.py#L22) — `SETTINGS.base_dir` default `Path('corpora')` (standalone korpsearch API, not used by this app's `depsearch_interface.py`)
- [korpsearch/search_statistics.py:150](../korpsearch/search_statistics.py#L150) — `--base-dir` default `Path('corpora')`

Not path-configurable, generated alongside the corpora dir regardless of location (no action needed, just be aware they'll be created relative to wherever `base_dir` points):
- `sub_corpora_size.pkl`, `*.corpus`, `*.indexes` files — written into `base_dir` by `utils.split_corpus`/korpsearch indexing.
- `cache/` directory — used by korpsearch's cache dir default (`Path('cache')`, e.g. [korpsearch/search_statistics.py:152](../korpsearch/search_statistics.py#L152), [korpsearch/trim_cache.py:40](../korpsearch/trim_cache.py#L40)); relative to cwd, not to `base_dir`.

## 2. Submodule/directory layout changes (e.g. `deptreepy` or `korpsearch` move)

| File | Variable | Current value |
|---|---|---|
| [utils.py:14](utils.py#L14) | `KORPSEARCH_FOLDER` | `"./korpsearch"` |
| [utils.py:15](utils.py#L15) | `DEPTREEPY_FOLDER` | `"."` |
| [../depsearch_interface.py:13](../depsearch_interface.py#L13) | `DEPTREEPY_PATH` | `"./deptreepy.py"` |

`deptreepy.py` lives at the repo root (not in a `deptreepy/` submodule folder), so both constants above just point at the repo root / root-level script. `deptreepy` is referenced from two places (`utils.py` and `depsearch_interface.py`) — keep both in sync if it moves. `korpsearch` is only referenced from `utils.py`.

Also relative-path-dependent (assume the process's cwd is the repo root — matters if the app is launched from elsewhere or the repo layout is restructured):
- [../depsearch_interface.py:115,202,270](../depsearch_interface.py#L115) — `subprocess.run([sys.executable, "depsearch.py", ...])` — literal relative filename, no path constant. Breaks if `depsearch_interface.py` isn't run with the repo root as cwd, or if `depsearch.py` moves relative to the repo root.
- [../depsearch_interface.py:370,375](../depsearch_interface.py#L370) — `StaticFiles(directory="depsearch_tools/static", ...)` / `FileResponse("depsearch_tools/static/index.html")` — frontend build output location, nested under `depsearch_tools/` since that's where `depsearch_tools/build_and_copy.py` and the `frontend/` source live.
- [build_and_copy.py:5-6](build_and_copy.py#L5) — `FRONTEND_DIR = "frontend"`, `BACKEND_STATIC_DIR = "./static"` — relative to `build_and_copy.py`'s own directory (`depsearch_tools/`), run this script with cwd `depsearch_tools/`. Must resolve to the same on-disk directory as the `static` paths above.
- [utils.py:16](utils.py#L16) — `TEMP_VOLUME_PATH = Path(__file__).resolve().parent / "temp_volume"` — self-locating via `__file__`, no action needed even if the repo moves, but the temp dir always sits next to `utils.py` (i.e. inside `depsearch_tools/`).
- [../depsearch_interface.py:15](../depsearch_interface.py#L15) — `VOLUME_DIR = str(Path(__file__).resolve().parent / "depsearch_tools" / "temp_volume")` — self-locating from the repo root, kept at the same location as `utils.TEMP_VOLUME_PATH` resolves to, or the API's temp output files and `depsearch.py`'s temp volume will diverge.
- [korpsearch/search_cmdline.py:14](../korpsearch/search_cmdline.py#L14) — `TEMP_VOLUME_PATH = Path(__file__).resolve().parent.parent / "depsearch_tools" / "temp_volume"` — **a second independent self-locating copy of the same path**, hardcoded inside the `korpsearch` submodule. `run_korpsearch()` shells out to this script, which writes each sub-corpus's matches here; `utils.merge_output_files()` then globs for those same files under its own `TEMP_VOLUME_PATH` above. If this and `utils.py`'s `TEMP_VOLUME_PATH` ever point at different directories, the merge silently finds zero files and every search returns empty results with no error (this exact bug happened when `utils.py` moved into `depsearch_tools/` but this copy wasn't updated to match — see git history).
- [../operations.py:22](../operations.py#L22) — `TEMP_VOLUME_PATH = Path(__file__).resolve().parent / "depsearch_tools" / "temp_volume"` — **a third independent self-locating copy**, in deptreepy's own core. `parse_operation`'s `extract_sentences` case, `preprocess_operation`, and `postprocess_operation` all read `context_size.pkl` from here (written by `utils._make_temp_volume`) to decide whether to run the context-aware code path (`conllu2treeswithindex` / `extract_sentences_with_context` / `treeswithindex2strs`) or the plain one. If this ever diverges from the other two, `context_size.pkl` is never found, `context_size` silently falls back to `0`, and **`--context-size N` queries stop returning any context, with no error** — this exact bug occurred and was fixed here.

All three `TEMP_VOLUME_PATH` copies (`utils.py`, `korpsearch/search_cmdline.py`, `operations.py`) and all three `DEFAULT_CORPORA_DIR`/`CORPORA_DIR` copies must keep resolving to the same physical directories if any of these files move.
