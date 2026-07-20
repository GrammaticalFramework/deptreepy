import argparse
from depsearch_tools.utils import build_indexes, search


def main(args: argparse.Namespace) -> None:
    match args.command:
        case 'build_indexes':
            build_indexes(args)
        case 'search':
            search(args)
        case _:
            print('Invalid command.')


parser = argparse.ArgumentParser()
parser.add_argument('--command', type=str, required=True,
                    help='The command to be executed.')
parser.add_argument('--corpus', nargs='+', required=True,
                    help='Corpus to work on')
parser.add_argument('--query', type=str)
parser.add_argument('--base-dir', type=str,
                    help='Base directory to work on. Default: ./corpora')
parser.add_argument('--suspend-intermediate-output', action='store_true',
                    help='Suspend the output of the searching-by-index process')
parser.add_argument('--suspend-infotext', action='store_true',
                    help='Hide the intermediate informing text')
parser.add_argument('--number-of-subcorpora', type=int, required=False,
                    help='Number of sub-corpora to divide while building indexes')
parser.add_argument('--context-size', type=int, required=False,
                    help='Number of surrounding elements to be included before and after a search result')
parser.add_argument('--id', type=str, required=False,
                    help='Unique identifier for the search session, used for temporary file naming')

if __name__ == "__main__":
    args = parser.parse_args()
    main(args)
