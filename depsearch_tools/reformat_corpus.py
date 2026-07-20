"""Streaming CoNLL-U corpus preprocessor.

This script combines two behaviors:
1. Normalize comments and ensure a comment exists before sentence-start token lines.
2. Remove invalid sentence blocks and normalize spacing between blocks.

Designed for very large input files: it processes one block at a time.
"""

from __future__ import annotations

import argparse
from typing import Iterable, List


DEFAULT_COMMENT = "# Dummy comment line\n"


def _normalize_comment_line(line: str) -> str:
    """Convert leading '###' to canonical '# ' comment form."""
    if line.startswith("###"):
        return "# " + line[3:]
    return line


def _has_valid_token(block: Iterable[str]) -> bool:
    """Return True if block has at least one real token row (integer ID)."""
    for line in block:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        parts = line.split("\t", 1)
        token_id = parts[0].strip() if parts else ""
        if token_id.isdigit():
            return True

    return False


def _prepare_block(block: List[str], fallback_comment: str) -> tuple[List[str], str]:
    """Normalize one block and ensure a comment before a leading '1\t' token."""
    processed: List[str] = []
    last_comment = fallback_comment
    seen_content = False

    for raw_line in block:
        line = _normalize_comment_line(raw_line)

        if line.startswith("#"):
            last_comment = line
            processed.append(line)
            seen_content = True
            continue

        # If the first content row is sentence token 1 and there is no
        # comment in this block yet, inject a fallback comment.
        if line.startswith("1\t") and not seen_content:
            processed.append(last_comment)

        processed.append(line)
        seen_content = True

    return processed, last_comment


def preprocess_conllu_file(input_file: str, output_file: str) -> None:
    """Preprocess CoNLL-U file in a memory-efficient streaming manner."""
    current_block: List[str] = []
    current_comment = DEFAULT_COMMENT
    wrote_block = False

    with open(input_file, "r", encoding="utf-8") as infile, open(
        output_file, "w", encoding="utf-8"
    ) as outfile:
        for line in infile:
            if line.strip() == "":
                if not current_block:
                    # Skip consecutive empty lines.
                    continue

                prepared_block, current_comment = _prepare_block(
                    current_block, current_comment
                )

                if _has_valid_token(prepared_block):
                    if wrote_block:
                        outfile.write("\n")
                    outfile.writelines(prepared_block)
                    wrote_block = True

                current_block = []
            else:
                current_block.append(line)

        # Flush the final block if file doesn't end with an empty line.
        if current_block:
            prepared_block, current_comment = _prepare_block(
                current_block, current_comment
            )
            if _has_valid_token(prepared_block):
                if wrote_block:
                    outfile.write("\n")
                outfile.writelines(prepared_block)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess CoNLL-U corpus with streaming block handling."
    )
    parser.add_argument("input_file", help="Path to input CoNLL-U file")
    parser.add_argument("output_file", help="Path to output CoNLL-U file")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    preprocess_conllu_file(args.input_file, args.output_file)
    print(f"Preprocessed CoNLL-U file saved to {args.output_file}")
