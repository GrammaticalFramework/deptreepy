# operations that transform dependency structures and can be piped if types match

import sys
import os  # temporarily, to call VisualizeUD.hs
from dataclasses import dataclass
from typing import Iterable, Callable
from trees import *
from patterns import *
from treetypes import treetype_statistics_dict, head_dep_statistics_dict
from visualize_ud import conll2svg
from udpipe2_client import process
from yaml import safe_load
from udpipe2_models import udpipe2_model
import pickle
from typing import List, Tuple, Dict, Any
from collections import deque, defaultdict
from pathlib import Path

# not used, letting UD-Pipe do sentence splitting
# from sentence_splitter import split_text_into_sentences

TEMP_VOLUME_PATH = Path(__file__).resolve().parent.parent / Path("temp_volume")
INTERMEDIATE_OUTPUT_PATH = TEMP_VOLUME_PATH / "intermediate_output"
DEFAULT_CORPORA_DIR = Path(__file__).resolve().parent.parent / "corpora"

def CoNLLUtoSentence(conllu_block: str) -> str:
    "convert a CoNLL-U block (one or more sentences) to plain text"

    def customwordlines2wordliness(lines: Iterable[WordLine]) -> Iterable[list[WordLine]]:
        "convert a stream of wordlines into a stream of lists of wordlines"
        oid = 0
        stanza = []
        for line in lines:
            try:
                id = ifint(line.ID)
            except ValueError:
                continue
            if id > oid:
                stanza.append(line)
                oid = id
            else:
                yield stanza
                stanza = [line]
                oid = id
        if stanza:
            yield stanza

    wordlines = conllu2wordlines(conllu_block.splitlines())
    sentences = wordlines2sentences(customwordlines2wordliness(wordlines))
    return " ".join(sentences)


def get_context(
    global_index: Iterable[int],
    context_size: int = 0,
    corpus: str = "example_corpus",
    base_dir: str = DEFAULT_CORPORA_DIR,
    search_id: str | None = None
) -> List[Tuple[str, str, str]]:
    """
    Get the full text of a tree (or a subtree's ancestor) and the surrounding context.

    (base_dir and corpus name is read from TEMP_VOLUME_PATH / Path(search_id) if search_id is specified)

    Reads {base_dir}/{corpus}.csv as *text*, 
    where sentences are in CoNLL-U format and an empty line separates sentences 
    (and defines the global sentence index starting at 0).

    For each central sentence index i in `global_index`, returns a tuple:
      (preceding_context_text, central_sentence_text, following_context_text)

    where:
      - preceding_context_text includes up to `context_size` sentences before i
      - following_context_text includes up to `context_size` sentences after i
      - contexts are automatically clipped at corpus boundaries
      - duplicates in `global_index` are preserved (same output repeated accordingly)
    """
    if search_id is not None:
        temp_volume_path = TEMP_VOLUME_PATH / Path(search_id)
    else:
        temp_volume_path = TEMP_VOLUME_PATH

    base_dir_pkl_path = temp_volume_path / Path("base_dir.pkl")
    corpus_pkl_path = temp_volume_path / Path("corpus.pkl")
    context_size_pkl_path = temp_volume_path / Path("context_size.pkl")

    if os.path.exists(base_dir_pkl_path):
        with open(base_dir_pkl_path, "rb") as f:
            base_dir = pickle.load(f)
    if os.path.exists(corpus_pkl_path):
        with open(corpus_pkl_path, "rb") as f:
            corpus = pickle.load(f)
    if os.path.exists(context_size_pkl_path):
        with open(context_size_pkl_path, "rb") as f:
            context_size = pickle.load(f)
    if context_size < 0:
        raise ValueError("context_size must be >= 0")

    indices = list(global_index)
    if not indices:
        return []
    
    # Keep duplicates: map each central index -> positions in output list
    positions_by_central: Dict[int, List[int]] = defaultdict(list)
    for pos, idx in enumerate(indices):
        if idx < 0:
            raise ValueError(f"global_index contains a negative sentence index: {idx}")
        positions_by_central[idx].append(pos)

    out: List[Tuple[str, str, str] | None] = [None] * len(indices)

    # Rolling buffer of previous sentences (up to context_size): (sent_idx, sent_conllu_block)
    prev_buf: deque[Tuple[int, str]] = deque(maxlen=context_size)

    # Pending requests: central_idx -> data dict
    # Each pending lives until we have read up to central_idx + context_size (or EOF).
    pending: Dict[int, Dict[str, Any]] = {}
    active_centrals: deque[int] = deque()  # centrals in increasing order as encountered

    def _to_text(conllu_block: str) -> str:
        # CoNLLUtoSentence is assumed to accept one or more sentences in CoNLL-U form
        if not conllu_block:
            return ""
        return CoNLLUtoSentence(conllu_block)

    def _join_sent_blocks(blocks: List[str]) -> str:
        # Keep CoNLL-U sentence separation semantics: blank line between sentences
        return "\n\n".join(b for b in blocks if b)

    def _finalize(central_idx: int) -> None:
        data = pending.pop(central_idx, None)
        if data is None:
            return

        preceding_conllu = _join_sent_blocks(data["preceding_blocks"])
        central_conllu = data["central_block"] + '\n'
        following_conllu = _join_sent_blocks(data["following_blocks"])
        triple = (_to_text(preceding_conllu), _to_text(central_conllu), _to_text(following_conllu))

        for pos in positions_by_central.get(central_idx, []):
            out[pos] = triple

    file_path = Path(base_dir) / Path(f"{corpus}.csv")

    # --- Stream parse sentence blocks (CoNLL-U separated by blank line) ---
    current_lines: List[str] = []
    sent_idx = 0

    def _handle_sentence_block(block: str, idx: int) -> None:
        nonlocal prev_buf, pending, active_centrals

        # 1) For all currently pending centrals, add this as "following" if within window.
        # Active centrals are those we've started (we saw the central sentence in the stream)
        # and haven't expired yet.
        # We also prune expired centrals from the left as we advance.
        while active_centrals:
            c0 = active_centrals[0]
            if idx > c0 + context_size:
                # already past its window; it should have been finalized earlier,
                # but finalize defensively
                _finalize(c0)
                active_centrals.popleft()
            else:
                break

        if context_size > 0 and active_centrals:
            for c in active_centrals:
                if c < idx <= c + context_size:
                    pending[c]["following_blocks"].append(block)

        # 2) If this sentence is requested as a central, start a pending window
        if idx in positions_by_central and idx not in pending:
            # Collect up to context_size preceding sentences from prev_buf
            preceding_blocks = [b for (_i, b) in prev_buf]  # already clipped by deque maxlen
            pending[idx] = {
                "preceding_blocks": preceding_blocks,
                "central_block": block,
                "following_blocks": [],
            }
            active_centrals.append(idx)

        # 3) If this sentence completes any window (idx == central + context_size), finalize.
        if context_size >= 0 and active_centrals:
            # Multiple centrals can complete at this idx
            while active_centrals:
                c0 = active_centrals[0]
                if idx >= c0 + context_size:
                    _finalize(c0)
                    active_centrals.popleft()
                else:
                    break

        # 4) Update rolling buffer
        if context_size > 0:
            prev_buf.append((idx, block))

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            # Sentence boundary: truly empty line after stripping whitespace.
            # (If your CSV uses empty rows as sentence separators, this works.)
            if line.strip() == "":
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    _handle_sentence_block(block, sent_idx)
                    sent_idx += 1
                    current_lines = []
                else:
                    # multiple blank lines: ignore
                    continue
            else:
                current_lines.append(line)

        # Flush last sentence if file doesn't end with blank line
        if current_lines:
            block = "\n".join(current_lines).strip()
            _handle_sentence_block(block, sent_idx)
            sent_idx += 1

    # EOF: finalize any pending windows with truncated following context
    while active_centrals:
        c = active_centrals.popleft()
        _finalize(c)

    # Sanity: all requested indices should have been within range per your assumption
    # but if not, raise a helpful error.
    missing = [i for i, v in enumerate(out) if v is None]
    if missing:
        bad_idxs = sorted({indices[i] for i in missing})
        raise IndexError(
            "Some requested global_index values were not found in the corpus "
            f"(out of range or parsing mismatch). Missing indices: {bad_idxs}"
        )

    # mypy: out is fully populated now
    return out  # type: ignore[return-value]


@dataclass
class Operation:
    "typed stream operations"
    oper: Callable
    argtype: type
    valtype: type
    name: str
    doc: str
    
    def __call__(self, arg):
        return self.oper(arg)
    def __doc__(self):
        return doc

    def pipe_two(self, oper2):
        "apply self, then apply another operation on the result"
        if (t1 := self.valtype) == (t2 := oper2.argtype):
            return Operation(
                lambda x: oper2(self(x)),
                self.argtype,
                oper2.valtype,
                self.name + ' | ' + oper2.name,
                '\n'.join([self.doc, 'then' + oper2.doc])
                )
        else:
            raise TypeError(' '.join(
                ['output type', str(t1), 'of', self.name,
                     'does not match input type', str(t2), 'of', oper2.name]))
        
    def __mul__(self, oper1):
        return pipe_two(oper1, self)
        
    
def operation(f: Callable) -> Operation:
    "a decorator that makes a one-argument function into an operation"
    if len(anns := f.__annotations__) == 2 and 'return' in anns:
        return Operation(
                f,
                list(anns.values())[0],
                anns['return'],
                f.__name__,
                f.__doc__)
    else:
        raise TypeError("expected type-decorated one-argument function, found " + f.__name__)

    
def pipe(opers: list[Operation]) -> Operation:
    "pipe a list of operations together"
    oper = opers[0]
    for oper2 in opers[1:]:
        oper = oper.pipe_two(oper2)
    return oper


# CoNLL-U input is a stream of lines representing a valid stream of trees
CoNLLU = Iterable[str]


@operation
def conllu2wordlines(lines: CoNLLU) -> Iterable[WordLine]:
    "read a sequence of strings as WordLines, ignoring failed ones"
    for line in lines:
        try:
            word = read_wordline(line)
            yield word
        except:
            pass


@operation
def conllu2trees(lines: CoNLLU) -> Iterable[DepTree]:
    "convert a stream of lines into a stream of deptrees"
    comms = []
    nodes = []
    for line in lines:
        if line.startswith('#'):
            comms.append(line.strip())
        elif line.strip():
            t = read_wordline(line)
            nodes.append(t)
        else:
            dt = build_deptree(nodes)
            dt.comments = comms
            yield dt
            comms = []
            nodes = []


def conllu2treeswithindex(search_id: str | None = None) -> Operation:
    def _conllu2treeswithindex(lines: CoNLLU) -> Iterable[DepTree]:
        comms = []
        nodes = []
        global_indexes = []
        corpus = "example_corpus"

        temp_volume_path = (TEMP_VOLUME_PATH / search_id) if search_id is not None else TEMP_VOLUME_PATH

        corpus_pkl_path = temp_volume_path / "corpus.pkl"

        if os.path.exists(corpus_pkl_path):
            with open(corpus_pkl_path, "rb") as f:
                corpus = pickle.load(f)

        search_id_suffix = f"_{search_id}" if search_id is not None else ""
        output_indices_pkl = INTERMEDIATE_OUTPUT_PATH / f"{corpus}_output_indices{search_id_suffix}.pkl"
        if os.path.exists(output_indices_pkl):
            with open(output_indices_pkl, "rb") as f:
                global_indexes = pickle.load(f)

        for line in lines:
            if line.startswith('#'):
                comms.append(line.strip())
            elif line.strip():
                t = read_wordline(line)
                nodes.append(t)
            else:
                current_gb = global_indexes.pop(0) if global_indexes else -1
                dt = build_deptree_for_depsearch(nodes, comms, current_gb)
                yield dt
                comms = []
                nodes = []

    return Operation(
        _conllu2treeswithindex,
        CoNLLU,
        Iterable[DepTree],
        "conllu2treeswithindex",
        "convert a stream of lines into deptrees with global indexes",
    )
            
@operation
def wordlines2wordliness(lines: Iterable[WordLine]) -> Iterable[list[WordLine]]:
    "convert a stream of wordlines into a stream of lists of wordlines"
    oid = 0
    stanza = []
    for line in lines:
        id = ifint(line.ID)
        if id > oid:
            stanza.append(line)
            oid = id
        else:
            yield stanza
            stanza = [line]
            oid = id


@operation
def wordlines2strs(lines: Iterable[WordLine]) -> Iterable[str]:
    "convert wordlines to tab-separated strings line by line"
    for line in lines:
        yield str(line)

        
@operation
def trees2strs(trees: Iterable[DepTree]) -> Iterable[str]:
    "convert wordlines to tab-separated strings line by line"
    for tree in trees:
        yield str(tree)
        yield ''


def treeswithindex2strs(search_id: str | None = None) -> Operation:
    def _treeswithindex2strs(trees: Iterable[DepTree]) -> Iterable[str]:
        "convert wordlines to tab-separated strings line by line, include context"
        trees = list(trees) # change generator to list, may consider better solution later
        global_indexes = [tree.global_index for tree in trees]
        context = get_context(global_indexes, search_id=search_id)
        count = 0
        for tree in trees:
            tree.context = context[count] if count < len(context) else None
            count += 1
            yield str(tree)
            yield ''

    return Operation(
        _treeswithindex2strs,
        Iterable[DepTree],
        Iterable[str],
        "treeswithindex2strs",
        "convert wordlines to tab-separated strings line by line, include context",
    )


@operation
def trees2wordliness(trees: Iterable[DepTree]) -> Iterable[list[WordLine]]:
    "convert a stream of deptrees to a stream of relabeled lists of wordlines"
    for tree in trees:
        tree = relabel_deptree(tree)
        yield tree.wordlines()


@operation
def trees2conllu(trees: Iterable[DepTree]) -> Iterable[str]:
    "convert a stream of deptrees to a stream of relabeled lists of wordlines"
    for tree in trees:
        tree = relabel_deptree(tree)
        for line in tree.comments + list(map(str, tree.wordlines())):
            yield line
        yield ''


@operation
def trees2wordlines(trees: Iterable[DepTree]) -> Iterable[WordLine]:
    "convert a stream of deptrees to a stream wordlines"
    for tree in trees:
        for line in tree.wordlines():
            yield line


@operation
def wordliness2conllu(stanzas: Iterable[list[WordLine]]) -> CoNLLU:
    "convert a stream of lists of wordlines to relabelled empty-line-separated stanzas"
    for ws in stanzas:
        yield '# ' + ' '.join([w.FORM for w in ws])
        for w in ws:
            yield str(w)
        yield ''
        

@operation
def wordlines2sentences(wordliness: Iterable[list[WordLine]]) -> Iterable[str]:
    "extract sentences from a stream of lists of wordlines, using the FORM fields"
    for wordlines in wordliness:
        yield ' '.join([word.FORM for word in wordlines])


# operation that extracts a sentence from a dependency tree
extract_sentences : Operation = pipe([trees2wordliness, wordlines2sentences])


def extract_sentences_with_context(search_id: str | None = None, include_metadata: bool = False) -> Operation:
    def _extract_sentences_with_context(trees: Iterable[DepTree]) -> Iterable[str]:
        "extract sentences with context from a stream of trees, using the FORM fields"
        trees = list(trees) # change generator to list, may consider better solution later
        global_indexes = [tree.global_index for tree in trees]
        context = get_context(global_indexes, search_id=search_id)
        extracted_matches = extract_sentences(trees)
        _include_metadata = include_metadata
        count = 0
        for extracted_match in extracted_matches:
            pre_context, cen_context, post_context = context[count] if count < len(context) else (None, None, None)
            if cen_context is not None:
                cen_context = cen_context.replace(extracted_match, f"**{extracted_match}**")
                complete_string = cen_context
                if pre_context is not None:
                    complete_string = pre_context + "\n" + complete_string
                if post_context is not None:
                    complete_string = complete_string + "\n" + post_context

                if _include_metadata:
                    complete_string = "\n".join(trees[count].comments) + "\n" + complete_string
                yield complete_string
                yield ''
            else:
                yield "OUT OF CONTEXT RANGE"
                yield ''
            count += 1

    return Operation(
        _extract_sentences_with_context,
        Iterable[DepTree],
        Iterable[str],
        "extract_sentences_with_context",
        "extract sentences with context from a stream of trees",
    )

@operation
def extract_sentences_with_metadata(trees: Iterable[DepTree]) -> Iterable[str]:
    "extract sentences with metadata from a stream of trees, using the FORM fields"
    for tree in trees:
        metadata_string = "\n".join(tree.comments)
        sentence_string = ' '.join([word.FORM for word in tree.wordlines()])
        yield metadata_string + '\n' + sentence_string
        yield ''


@operation
def underscore_fields(fields: list[str]) -> Operation:
    return Operation (
        lambda ws: (replace_by_underscores(fields, w) for w in ws),
        Iterable[WordLine],
        Iterable[WordLine],
        "underscore fields",
        "replace the values of given fields by underscores"
        )


@operation
def extract_fields(fields: list[str]) -> Operation:
    fields = [f for f in WORDLINE_FIELDS if f not in fields]
    return Operation (
        lambda ws: (replace_by_underscores(fields, w) for w in ws),
        Iterable[WordLine],
        Iterable[WordLine],
        "underscore fields",
        "replace the values of given fields by underscores"
        )


def take_trees(begin: int, end: int) -> Operation:
    
    def take(ts):
        i = begin
        while i < end:
            yield(next(ts))
            i += 1
            
    return Operation (
        take,
        Iterable[DepTree],
        Iterable[DepTree],
        "take_trees",
        "take a selection of trees from <begin> to <end>-1 (counting from 0)"
        )

        
def statistics(fields: list[str]) -> Operation:
    return Operation (
        lambda ws: sorted_statistics(wordline_statistics(fields, ws)),
        Iterable[WordLine],
        list,
        'statistics',
        "frequency table of a combination of fields, sorted as a list in descending order"
        )


def ngram_statistics(n: int, fields: list[str]) -> Operation:
    return Operation (
        lambda ws: sorted_statistics(wordline_ngram_statistics(fields,
                        wordline_ngrams(n, wordlines2wordliness(ws)))),
        Iterable[WordLine],
        list,
        'statistics',
        "frequency table of ngrams of combinations of fields in stanzas, sorted as a list in descending order"
        )


def tree_ngram_statistics(n: int, fields: list[str]) -> Operation:
    return Operation (
        lambda ws: sorted_statistics(wordline_ngram_statistics(fields, ngrams(n, ws))),
        Iterable[DepTree],
        list,
        'statistics',
        "frequency table of ngrams of combinations of fields in trees, sorted as a list in descending order"
        )


def treetype_statistics(fields: list[str]) -> Operation:
    return Operation(
        lambda trees: sorted_statistics(treetype_statistics_dict(trees, fields)),
        Iterable[DepTree],
        list,
        'treetype_statistics',
        "frequency table of types of trees and subtrees, field* as atomic type"    
        )


def head_dep_statistics(fields: list[str]) -> Operation:
    return Operation(
        lambda trees: sorted_statistics(head_dep_statistics_dict(trees, fields)),
        Iterable[DepTree],
        list,
        'head_dep_statistics',
        "frequency table of types of head-dependent pairs, field* as atomic type"    
        )


def count_wordlines() -> Operation:
    return Operation (
        lambda ws: [len(list(ws))],
        Iterable[WordLine],
        list[int],
        'count_wordlines',
        "return the number of wordlines"
        )


def count_trees() -> Operation:
    return Operation (
        lambda ws: [len(list(ws))],
        Iterable[DepTree],
        list[int],
        'count_trees',
        "return the number of trees"
        )


def match_wordlines(patt: Pattern) -> Operation:
    return Operation (
        lambda ws: (w for w in ws if match_wordline(patt, w)),
        Iterable[WordLine],
        Iterable[WordLine],
        'match_wordlines',
        'pattern matching with wordlines, yielding the ones that match'
        )
        

def match_trees(patt: Pattern) -> Operation:

    def matcht(ts):
        for tr in ts:
            for t in matches_of_deptree(patt, tr):
                yield t
                
    return Operation (
        matcht,
        Iterable[DepTree],
        Iterable[DepTree],
        'match_trees',
        'pattern matching with entire trees, yielding the ones that match'
        )


def match_subtrees(patt: Pattern) -> Operation:

    def matcht(ts):
        for tr in ts:
            for t in matches_in_deptree(patt, tr):
                yield t
                
    return Operation (
        matcht,
        Iterable[DepTree],
        Iterable[DepTree],
        'match_subtrees',
        'pattern matching with trees and subtrees, yielding the ones that match'
        )


def match_found_in_tree(patt: Pattern) -> Operation:

    def matcht(ts):
        for tr in ts:
            for t in match_found_in_deptree(patt, tr):
                yield t
                
    return Operation (
        matcht,
        Iterable[DepTree],
        Iterable[DepTree],
        'match_found_in_tree',
        'pattern matching inside trees, yielding the ones where some subtree matches'
        )


def match_segments(patt: Pattern) -> Operation:
    def matcht(ts):
        for segm in matches_in_tree_stream(patt, ts):
            segm[0].prefix_comments(['# FIRST IN SEGMENT length ' + str(len(segm))])
            segm[-1].prefix_comments(['# LAST IN SEGMENT'])
            for tree in segm:
                yield tree
    return Operation(
        matcht,
        Iterable[DepTree],
        Iterable[DepTree],
        'match_segments',
        'pattern matching contiguous segments, marking the ones that match'
        )
        

def change_wordlines(patt: Pattern) -> Operation:
    return Operation (
        lambda ws: (change_wordline(patt, w) for w in ws),
        Iterable[WordLine],
        Iterable[WordLine],
        'change_wordlines',
        'pattern-based changes in wordlines'
        )    


def change_trees(patt: Pattern) -> Operation:
    return Operation (
        lambda ws: (change_deptree(patt, w) for w in ws),
        Iterable[DepTree],
        Iterable[DepTree],
        'change_subtrees',
        'pattern-based changes in trees (no recursion to subtrees)'
        )


def change_subtrees(patt: Pattern) -> Operation:
    return Operation (
        lambda ws: (changes_in_deptree(patt, w) for w in ws),
        Iterable[DepTree],
        Iterable[DepTree],
        'change_subtrees',
        'pattern-based changes recursively in subtrees, top-down'
        )

def find_paths(patts: [Pattern]) -> Operation:
    return Operation (
        lambda ts: (p for t in ts for p in find_paths_in_subtrees(patts, t)),
        Iterable[DepTree],
        Iterable[DepTree],
        'find_subtrees',
        'find paths matching sequences of patterns'
        )

def find_partial_subtrees(patts: [Pattern]) -> Operation:
    return Operation (
        lambda ts: (p for t in ts for p in find_partial_local_subtrees(patts, t)),
        Iterable[DepTree],
        Iterable[DepTree],
        'find_partial_subtrees',
        'find partial subtrees matching tree patterns'
        )


@operation
def visualize_conllu(s: Iterable[str]) -> Iterable[str]:
    'show CoNLLU as SVG in HTML'
    s = '\n'.join([s.strip() for s in s])  ## type of conll2svg should be It[str] 
    return conll2svg(s)


def txt2conllu_model(model: str, corpus: Iterable[str]) -> CoNLLU:
    "parse a raw text corpus into CoNNL-U, using UDPipe2"
    corpus = '\n'.join([line.strip() for line in corpus])
    udpipe2_params = {
        "data": corpus,
        "model": model,
        # empty strings (as opposed to None) will enable these components)
        "tokenizer": "", "parser": "", "tagger": "",
        "outfile": None, # stdout
        "service": "https://lindat.mff.cuni.cz/services/udpipe/api"
    }
    parsed = process(udpipe2_params)
    for line in parsed.split("\n"):
        yield line


# the original definition by Arianna
@operation
def txt2conllu_yaml(corpus: Iterable[str]) -> CoNLLU:
    "parse a raw text corpus into CoNNL-U, using UDPipe2"
    with open("udpipe2_params.yaml") as f:
        udpipe2_params = safe_load(f)
        model = udpipe2_params['model']
    for c in txt2conllu_model(model, corpus):
        yield c

    
def txt2conllu(langname: str) -> Operation:
    model = udpipe2_model(langname)
    return Operation (
        lambda corpus: txt2conllu_model(model, corpus),
        Iterable[str],
        Iterable[WordLine],
        "parse text to CoNLLU",
        "parse a raw text corpus into CoNLL-U, using UDPipe2"
        )


def from_script(filename: str) -> Operation:
    "reads an operation by parsing a file"
    with open(filename) as script:
        return parse_operation_pipe(script.read())
            

def parse_operation(ss: list[str]) -> Operation:
    "operation parser for files and command line arguments"
    match ss:
        case ['count_wordlines', *ww]:
            return count_wordlines()
        case ['count_trees', *ww]:
            return count_trees()
        case ['match_wordlines', *ww]:
            return match_wordlines(parse_pattern(' '.join([*ww])))
        case ['match_subtrees', *ww]:
            return match_subtrees(parse_pattern(' '.join([*ww])))
        case ['match_found_in_tree', *ww]:
            return match_found_in_tree(parse_pattern(' '.join([*ww])))
        case ['match_trees', *ww]:
            return match_trees(parse_pattern(' '.join([*ww])))
        case ['match_segments', *ww]:
            return match_segments(parse_pattern(' '.join([*ww])))
        case ['change_wordlines', *ww]:
            return change_wordlines(parse_pattern(' '.join([*ww])))
        case ['change_trees', *ww]:
            return change_trees(parse_pattern(' '.join([*ww])))
        case ['change_subtrees', *ww]:
            return change_subtrees(parse_pattern(' '.join([*ww])))
        case ['find_paths', *ww]:
            return find_paths(
                parse_pattern(' '.join(['PATH'] + [*ww])).subtrees)   
        case ['find_partial_subtrees', *ww]:
            return find_partial_subtrees(
                parse_pattern(' '.join(['PATH'] + [*ww])).subtrees)   
        case ['extract_sentences']:
            return extract_sentences
        case ['trees2conllu']:
            return trees2conllu
        case ['trees2wordlines']:
            return trees2wordlines
        case ['take_trees', begin, end]:
            return take_trees(int(begin), int(end))
        case ['statistics', *ww]:
            return statistics(ww)
        case ['ngram_statistics', n, *ww]:
            return ngram_statistics(int(n), ww)
        case ['tree_ngram_statistics', n, *ww]:
            return tree_ngram_statistics(int(n), ww)
        case ['treetype_statistics', *ww]:
            return treetype_statistics(ww)
        case ['head_dep_statistics', *ww]:
            return head_dep_statistics(ww)
        case ['extract_fields', *ww]:
            return extract_fields(ww)
        case ['underscore_fields', *ww]:
            return underscore_fields(ww)
        case ['visualize_conllu']:
            return visualize_conllu
        case ['from_script', filename]:
            return from_script(filename)
        case ['txt2conllu', langname]:
            return txt2conllu(langname)
        case ['txt2conllu']:
            return txt2conllu_yaml
        case ['conllu2trees']:
            return conllu2trees
        case _:
            raise ParseError(' '.join(['operation'] + ss + ['not matched']))


def parse_operation_pipe(s: str) -> Operation:
    "parsing operation pipes separated by |"
    return pipe([parse_operation(op.split()) for op in s.split('|')])


def preprocess_operation(op: Operation) -> Operation:
    "convert file-like input into type expected by operation"
    if op.argtype == Iterable[WordLine]:
        return pipe([conllu2wordlines, op])
    elif op.argtype == Iterable[DepTree]:
        return pipe([conllu2trees, op])
    else:
        return op

    
def postprocess_operation(op: Operation) -> Operation:
    "convert the output of operations to strings"
    if op.valtype == Iterable[WordLine]:
        return pipe([op, wordlines2strs])
    elif op.valtype == Iterable[DepTree]:
        return pipe([op, trees2strs])
    elif op.valtype == Iterable[list[WordLine]]:
        return pipe([op, wordliness2conllu]) 
    else:
        return op

    
# an example of "static typing", i.e. checked and rejected before applied to input
# invalid_operation = pipe([conllu2wordlines, conllu2wordlines])


def execute_pipe_on_strings(command: str, strs: Iterable[str]):
    "apply a command to a stream of strings, with pre- and postprocessing if needed"
    oper = parse_operation_pipe(command)
    oper = preprocess_operation(oper)
    oper = postprocess_operation(oper)
    print('# ', oper)

    for t in oper(strs):
        print(t)


