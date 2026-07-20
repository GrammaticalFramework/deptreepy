import shutil
import pickle
import subprocess
import os
import argparse
import multiprocessing
from pathlib import Path
import glob
import uuid

from depsearch_tools.query import extract_query

DEFAULT_CORPORA_DIR = str(Path(__file__).resolve().parent.parent / "corpora")
KORPSEARCH_FOLDER = "./korpsearch"
DEPTREEPY_FOLDER = "."
TEMP_VOLUME_PATH = Path(__file__).resolve().parent / Path("temp_volume")
INTERMEDIATE_OUTPUT_PATH = TEMP_VOLUME_PATH / "intermediate_output"


def get_cpu_count() -> int:
    """Return available CPU count"""
    return max(1, multiprocessing.cpu_count())


def clean_previous_indexing_files(corpus: str, base_dir: str) -> None:
    """
    Remove all files and directories inside base_dir whose names start with
    `corpus`, except the file whose base name is exactly `corpus`.
    """
    if not os.path.isdir(base_dir):
        raise ValueError(f"{base_dir} is not a valid directory")

    for name in os.listdir(base_dir):
        if not name.startswith(corpus):
            continue

        full_path = os.path.join(base_dir, name)
        base_name, _ = os.path.splitext(name)

        if os.path.isfile(full_path) and base_name == corpus:
            continue

        if os.path.isfile(full_path) or os.path.islink(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)


def split_corpus(
    num_parts: int,
    corpus: str,
    base_dir: str = DEFAULT_CORPORA_DIR,
    target_suffix: str = ".csv",
) -> list[Path]:
    """
    Split a CoNLL-U CSV file into `num_parts` chunks, preserving sentence
    boundaries (sentences are separated by blank lines in the source file).
    Returns a list of paths to the output chunk files.
    """
    if not corpus.endswith(target_suffix):
        corpus += target_suffix

    input_path = Path(base_dir) / corpus

    if not input_path.is_file():
        raise FileNotFoundError(f"Corpus file not found: {input_path}")

    clean_previous_indexing_files(Path(corpus).stem, base_dir)

    header = "\t".join(["id", "form", "lemma", "pos", "xpos", "feats",
                         "head", "deprel", "deps", "misc"]) + "\n"

    with open(input_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Group lines into per-sentence blocks (separated by blank lines)
    sentences, current = [], []
    for line in lines:
        if line.strip() == "":
            if current:
                sentences.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sentences.append(current)

    chunk_size = len(sentences) // num_parts
    output_files = []

    for i in range(num_parts):
        start = i * chunk_size
        end = None if i == num_parts - 1 else (i + 1) * chunk_size
        chunk = sentences[start:end]

        output_path = Path(base_dir) / f"{Path(corpus).stem}_{i}.csv"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            for sentence in chunk:
                f.writelines(sentence)
                f.write("\n")

        output_files.append(output_path)

    with open(Path(base_dir) / "sub_corpora_size.pkl", "wb") as f:
        pickle.dump(chunk_size, f)

    return output_files


def build_corpus_indexes(corpus: Path) -> None:
    """Build korp-search unary indexes for one sub-corpus."""
    subprocess.run(
        ["python3", Path(KORPSEARCH_FOLDER) / "build_indexes.py" ,
         "--corpus", corpus, "--corpus-index", "--reversed-features",
         "--base-dir", "."],
        check=True,
    )


def build_inverted_indexes(corpus: Path) -> None:
    """Build korp-search binary (pairwise feature) indexes for one sub-corpus."""
    subprocess.run(
        ["python3", Path(KORPSEARCH_FOLDER) / "build_indexes.py",
         "--corpus", corpus,
         "--features", "form", "lemma", "pos", "xpos", "feats", "deprel",
         "form_reversed", "lemma_reversed", "pos_reversed", "xpos_reversed", 
         "feats_reversed", "deprel_reversed","--max-dist", "0", "--base-dir", "."],
        check=True,
    )


def indexing_dispatcher(corpus: Path) -> None:
    """Build both unary and binary indexes for one sub-corpus."""
    build_corpus_indexes(corpus)
    build_inverted_indexes(corpus)


def build_indexes(args: argparse.Namespace) -> None:
    """Split each corpus into sub-corpora and build indexes in parallel."""
    num_parts = args.number_of_subcorpora or (get_cpu_count() * 4)
    base_dir = args.base_dir or DEFAULT_CORPORA_DIR

    for corpus in args.corpus:
        if not args.suspend_infotext:
            print(f"Splitting the {corpus} corpus into sub-corpora...")
        sub_corpora = split_corpus(num_parts, corpus, base_dir)

        if not args.suspend_infotext:
            print(f"Building indexes for {corpus} corpus...")
        with multiprocessing.Pool(num_parts) as pool:
            pool.starmap(indexing_dispatcher, [(sc,) for sc in sub_corpora])


def run_korpsearch(
    query: str,
    corpus: str,
    search_id: str,
    base_dir: str = DEFAULT_CORPORA_DIR,
    context_size: int = 0,
    suspend_output: bool = False,
) -> None:
    """Run korp-search on a single sub-corpus and write results to a file."""
    command = [
        "python3", Path(KORPSEARCH_FOLDER) / "search_cmdline.py",
        "--corpus", corpus,
        "--query", query,
        "--base-dir", base_dir,
        "--id", search_id,
        "--output-conllu-file",
        "--overwrite-file",
    ]
    if context_size > 0:
        command.append("--output-indices")

    kwargs = {"check": True}
    if suspend_output:
        kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run(command, **kwargs)


def _load_sub_corpora_size(base_dir: str) -> int:
    """Load the cached per-chunk sentence count, raising if missing."""
    size_file = f"{base_dir}/sub_corpora_size.pkl"
    if not os.path.exists(size_file):
        raise FileNotFoundError(
            f"Sub-corpora size file not found: {size_file}. "
            "Unable to work with context. Consider rebuilding indexes."
        )
    with open(size_file, "rb") as f:
        return pickle.load(f)


def merge_output_files(corpus: str, search_id: str) -> None:
    """Merge per-sub-corpus CoNLL-U result files into a single output file."""
    INTERMEDIATE_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    input_files = sorted(glob.glob(f"{INTERMEDIATE_OUTPUT_PATH}/{corpus}_*_output_{search_id}"))
    output_file = f"{INTERMEDIATE_OUTPUT_PATH}/{corpus}_output_{search_id}"

    with open(output_file, "w") as outfile:
        for fname in input_files:
            with open(fname) as infile:
                lines = infile.readlines()
                if len(lines) > 1:
                    outfile.writelines(lines)

    for fname in input_files:
        if os.path.exists(fname):
            os.remove(fname)


def merge_output_indices_files(corpus: str, base_dir: str, search_id: str) -> None:
    """
    Merge per-sub-corpus index pickle files into a single global-index file.
    Each sub-corpus index is offset by (chunk_size * sub_file_index) so that
    indices refer to sentence positions in the full corpus.
    """
    input_files = sorted(glob.glob(
        f"{INTERMEDIATE_OUTPUT_PATH}/{corpus}_*_output_indices_{search_id}.pkl"
    ))
    output_file = f"{INTERMEDIATE_OUTPUT_PATH}/{corpus}_output_indices_{search_id}.pkl"
    sub_corpora_size = _load_sub_corpora_size(base_dir)

    global_indices = []
    for fname in input_files:
        # Sub-file index is encoded in the filename; critical w.r.t. filename syntax.
        sub_file_idx = int(fname.split("_")[-4])
        offset = sub_corpora_size * sub_file_idx
        with open(fname, "rb") as f:
            global_indices.extend(idx + offset for idx in pickle.load(f))

    if os.path.exists(output_file):
        os.remove(output_file)
    with open(output_file, "wb") as f:
        pickle.dump(global_indices, f)

    for fname in input_files:
        if os.path.exists(fname):
            os.remove(fname)


def is_empty_query(query: str) -> bool:
    """Return True if the CQP query contains no search constraints."""
    return query.strip() in {"", "[]", "[] []"}


def run_deptreepy(query: str, corpus: str, search_id: str) -> None:
    """Pipe a corpus file through deptreepy for dependency-tree filtering."""
    command = ["python3", Path(DEPTREEPY_FOLDER) / "deptreepy.py", query, search_id]
    with open(corpus, "rb") as corpus_file:
        subprocess.run(command, stdin=corpus_file, check=True)


def _make_temp_volume(search_id: str, base_dir: str, context_size: int) -> Path:
    """Create a fresh temp directory for this search and seed it with metadata."""
    temp_path = TEMP_VOLUME_PATH / search_id

    if temp_path.exists():
        shutil.rmtree(temp_path) if temp_path.is_dir() else temp_path.unlink()
    temp_path.mkdir(parents=True, exist_ok=True)

    with open(temp_path / "base_dir.pkl", "wb") as f:
        pickle.dump(base_dir, f)
    with open(temp_path / "context_size.pkl", "wb") as f:
        pickle.dump(context_size, f)

    return temp_path


def _cleanup_search_artifacts(
    corpus: str, search_id: str, temp_path: Path
) -> None:
    """Remove intermediate files produced during a single-corpus search."""
    for path in [
        INTERMEDIATE_OUTPUT_PATH / f"{corpus}_output_{search_id}",
        INTERMEDIATE_OUTPUT_PATH / f"{corpus}_output_indices_{search_id}.pkl",
    ]:
        if path.exists():
            path.unlink()

    if temp_path.exists():
        shutil.rmtree(temp_path) if temp_path.is_dir() else temp_path.unlink()


def search(args: argparse.Namespace) -> None:
    """
    Run a two-phase search (inverted-index pre-filter + dependency-tree filter)
    across one or more corpora.
    """
    base_dir = args.base_dir or DEFAULT_CORPORA_DIR
    search_id = args.id or "local"
    cqp_query = extract_query(args.query)

    context_size = 0
    if args.context_size is not None:
        if args.context_size < 0:
            print("Context size cannot be negative. Excluding context instead.")
        else:
            context_size = args.context_size

    temp_path = _make_temp_volume(search_id, base_dir, context_size)

    if not is_empty_query(cqp_query):
        if not args.suspend_infotext:
            print("Query for presearch:", cqp_query)

        for corpus in args.corpus:
            with open(temp_path / "corpus.pkl", "wb") as f:
                pickle.dump(corpus, f)

            num_parts = len(glob.glob(f"{base_dir}/{corpus}_*.corpus"))

            if not args.suspend_infotext:
                print(f"Searching with inverted index - {corpus}")

            with multiprocessing.Pool(num_parts) as pool:
                pool.starmap(
                    run_korpsearch,
                    [
                        (cqp_query, f"{corpus}_{i}", search_id, base_dir,
                         context_size, args.suspend_intermediate_output)
                        for i in range(num_parts)
                    ],
                )

            merge_output_files(corpus, search_id)
            if context_size > 0:
                merge_output_indices_files(corpus, base_dir, search_id)

            if not args.suspend_infotext:
                print(f"Searching with dependency tree - {corpus}")

            corpus_path = INTERMEDIATE_OUTPUT_PATH / f"{corpus}_output_{search_id}"
            run_deptreepy(args.query, str(corpus_path), search_id)
            _cleanup_search_artifacts(corpus, search_id, temp_path)

    else:
        if not args.suspend_infotext:
            print("Empty CQR query.")

        for corpus in args.corpus:
            if not args.suspend_infotext:
                print(f"Searching with dependency tree - {corpus}")

            corpus_path = Path(base_dir) / Path(corpus).with_suffix(".csv")
            indices_file = INTERMEDIATE_OUTPUT_PATH / f"{corpus}_output_indices_{search_id}.pkl"

            if context_size > 0:
                INTERMEDIATE_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
                # Build a full-range index spanning all sentences across all sub-corpora.
                num_sub_corpora = len(glob.glob(f"{base_dir}/{corpus}_*.csv"))
                sub_corpora_size = _load_sub_corpora_size(base_dir)
                sentence_indices = list(range(num_sub_corpora * (sub_corpora_size + 1)))
                with open(indices_file, "wb") as f:
                    pickle.dump(sentence_indices, f)

            run_deptreepy(args.query, str(corpus_path), search_id)

            if indices_file.exists():
                indices_file.unlink()

    # Final cleanup of the temp volume (may already be gone if non-empty path ran)
    if temp_path.exists():
        shutil.rmtree(temp_path) if temp_path.is_dir() else temp_path.unlink()
