from fastapi import FastAPI, Body, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import subprocess
import os
import re
import signal
import uuid

DEPTREEPY_PATH = "./deptreepy/deptreepy.py"
CORPORA_DIR = "./corpora"
VOLUME_DIR = "./temp_volume"

ALLOWED_LANGUAGES = {"eng", "fin"}
# Creating API
app = FastAPI()

# Tracks the depsearch.py subprocess for each in-flight query, keyed by request id,
# so /api/cancel-query can find and kill it (and its multiprocessing.Pool workers).
RUNNING_PROCESSES: dict[str, asyncio.subprocess.Process] = {}


class QueryCancelled(Exception):
    pass


async def run_search_process(command_args: list[str], output_path: str, request_id: str) -> None:
    """
    Run depsearch.py as an awaited asyncio subprocess (instead of a blocking
    subprocess.run) so the event loop stays free to handle a concurrent
    /api/cancel-query request while the search is running.
    """
    with open(output_path, "w", encoding="utf-8") as out_f:
        # start_new_session makes depsearch.py the leader of a new process group,
        # so cancellation can kill it together with its multiprocessing.Pool workers.
        proc = await asyncio.create_subprocess_exec(
            *command_args,
            stdout=out_f,
            start_new_session=True,
        )
        RUNNING_PROCESSES[request_id] = proc
        try:
            returncode = await proc.wait()
        finally:
            RUNNING_PROCESSES.pop(request_id, None)

    if returncode < 0 and -returncode in (signal.SIGTERM, signal.SIGKILL):
        raise QueryCancelled()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, command_args)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_allowed_corpora() -> set[str]:
    """Return the set of valid corpus names from the corpora directory."""
    base_dir = CORPORA_DIR
    pattern = re.compile(r'.*_\d+\.csv$')
    all_files = [f for f in os.listdir(base_dir) if f.endswith('.csv')]
    return {os.path.splitext(f)[0] for f in all_files if not pattern.match(f)}


def validate_corpus(corpus: str) -> None:
    """Raise HTTP 400 if corpus is not in the allowed set."""
    # FIX: prevents path traversal and command injection via corpus name.
    # User input is checked against the real on-disk list before being
    # passed to any subprocess call.
    allowed = get_allowed_corpora()
    if corpus not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown corpus: '{corpus}'. Must be one of: {sorted(allowed)}",
        )


@app.get("/api/corpora")
async def get_corpora():
    corpora = list(get_allowed_corpora())
    response_data = {"corpora": corpora}
    return response_data


@app.post("/api/basic-query")
async def query_response(
        corpus: str = Body(...),
        query: str = Body(...),
        context_size: int = Body(0),
        id: str = Body(None)
):
    validate_corpus(corpus)

    if id is None:
        id = str(uuid.uuid4())

    temp_file = os.path.join(VOLUME_DIR, f"output_{id}.txt")
    if os.path.exists(temp_file):
        os.remove(temp_file)
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)

    if not query.endswith("extract_sentences"):
        complete_query = query + " | extract_sentences"
    else:
        complete_query = query

    command_args = [
        "python3", "depsearch.py",
        "--command", "search",
        "--corpus", corpus,
        "--context-size", str(context_size),
        "--id", id,
        "--query", complete_query,
        "--suspend-intermediate-output",
        "--suspend-infotext",
    ]

    # print(command_args)

    try:
        await run_search_process(command_args, temp_file, id)
    except QueryCancelled:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise HTTPException(status_code=499, detail="Query was cancelled.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query execution failed. Check your corpus/query syntax. Error: {str(e)}"
        )

    lines = []
    try:
        with open(temp_file, "r", encoding="utf-8") as file:
            all_lines = [line.rstrip("\n") for line in file]
        header_idx = next((i for i, line in enumerate(all_lines) if line.startswith("#")), -1)
        lines = all_lines[header_idx + 1:] if header_idx >= 0 else []
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    if context_size == 0:
        sentences = [line for line in lines if line.strip() != ""]
        return {"sentences": sentences}

    # First split by one-or-more empty lines into blocks.
    sentences = []
    current_block = []
    for line in lines:
        if line.strip() == "":
            if current_block:
                sentences.append("\n".join(current_block))
                current_block = []
            continue
        current_block.append(line)
    if current_block:
        sentences.append("\n".join(current_block))

    return {"sentences": sentences}

@app.post("/api/string-query")
async def query_response(
        corpus: str = Body(...),
        query: str = Body(...),
        search_by: str = Body('Word'),
        context_size: int = Body(0),
        id: str = Body(None)
):
    validate_corpus(corpus)

    if id is None:
        id = str(uuid.uuid4())

    temp_file = os.path.join(VOLUME_DIR, f"output_{id}.txt")
    if os.path.exists(temp_file):
        os.remove(temp_file)
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)

    # From search string (query) to real queries passed to depsearch.py
    words_in_search_string = query.strip().split()

    if search_by == 'Word':
        search_query = "match_found_in_tree SUBSEQUENCE " + " ".join([f"(FORM {word})" for word in words_in_search_string])
    elif search_by == 'Lemma':    
        search_query = "match_found_in_tree SUBSEQUENCE " + " ".join([f"(LEMMA {word})" for word in words_in_search_string])
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search_by value: {search_by}. Must be 'Word' or 'Lemma'."
        )
    
    complete_query = search_query + " | extract_sentences"

    command_args = [
        "python3", "depsearch.py",
        "--command", "search",
        "--corpus", corpus,
        "--context-size", str(context_size),
        "--id", id,
        "--query", complete_query,
        "--suspend-intermediate-output",
        "--suspend-infotext",
    ]

    # print(command_args)

    try:
        await run_search_process(command_args, temp_file, id)
    except QueryCancelled:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise HTTPException(status_code=499, detail="Query was cancelled.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query execution failed. Check your corpus/query syntax. Error: {str(e)}"
        )

    lines = []
    try:
        with open(temp_file, "r", encoding="utf-8") as file:
            all_lines = [line.rstrip("\n") for line in file]
        header_idx = next((i for i, line in enumerate(all_lines) if line.startswith("#")), -1)
        new_lines = all_lines[header_idx + 1:] if header_idx >= 0 else []
        lines.extend(new_lines)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # Split by one-or-more empty lines into blocks.
    sentences = []
    current_block = []
    for line in lines:
        if line.strip() == "":
            if current_block:
                sentences.append("\n\n".join(current_block))
                current_block = []
            continue
        current_block.append(line)
    if current_block:
        sentences.append("\n\n".join(current_block))

    return {"sentences": sentences}

@app.post("/api/advanced-query")
async def query_response(
        corpus: str = Body(...),
        query: str = Body(...),
        context_size: int = Body(0),
        id: str = Body(None)
):
    validate_corpus(corpus)

    if id is None:
        id = str(uuid.uuid4())

    temp_file = os.path.join(VOLUME_DIR, f"output_{id}.txt")
    if os.path.exists(temp_file):
        os.remove(temp_file)
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)

    command_args = [
        "python3", "depsearch.py",
        "--command", "search",
        "--corpus", corpus,
        "--context-size", str(context_size),
        "--id", id,
        "--query", query,
        "--suspend-intermediate-output",
        "--suspend-infotext",
    ]

    # print(command_args)

    try:
        await run_search_process(command_args, temp_file, id)
    except QueryCancelled:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise HTTPException(status_code=499, detail="Query was cancelled.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Advanced query execution failed. Error: {str(e)}"
        )

    try:
        with open(temp_file, "r", encoding="utf-8") as f:
            content = f.read()
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return {"output": content}


@app.post("/api/cancel-query")
async def cancel_query(id: str = Body(..., embed=True)):
    proc = RUNNING_PROCESSES.get(id)
    if proc is None:
        return {"cancelled": False}

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass

    return {"cancelled": True}


@app.post("/api/dependency-parsing")
async def dependency_parsing_response(
        text: str = Body(...),
        language: str = Body(...),
        id: str = Body(None)
):
    
    if language not in ALLOWED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: '{language}'. Allowed: {sorted(ALLOWED_LANGUAGES)}",
        )
    
    try:
        parse_result = subprocess.run(
            ["python3", DEPTREEPY_PATH, f"txt2conllu {language}", "dummy_id"],
            input=text,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {e.stderr}",
        )

    try:
        visualize_result = subprocess.run(
            ["python3", DEPTREEPY_PATH, "visualize_conllu", "dummy_id"],
            input=parse_result.stdout,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visualization failed: {e.stderr}",
        )

    # Remove the first and third lines from the HTML output before returning.
    html_content = visualize_result.stdout or ""
    lines = html_content.splitlines()
    # keep all lines except indices 0 and 2 (first and third)
    filtered_lines = [line for i, line in enumerate(lines) if i not in (0, 2)]
    filtered_content = "\n".join(filtered_lines)

    return HTMLResponse(content=filtered_content, status_code=200)


# Serving static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# For client-side routing fallback (React SPA)
@app.get("/{full_path:path}")
def serve_react_app():
    return FileResponse("static/index.html")
