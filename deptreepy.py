#!/usr/bin/env python3

import sys
from trees import *
from patterns import *
from operations import execute_pipe_on_strings

def print_help_message():
    with open('README.md') as file:
        for line in file.readlines()[9:-1]:
            print(line, end='')


# the new command interpreter, supporting pipes
if __name__ == '__main__':
    if not sys.argv[1:]:
        print_help_message()
    else:
      match sys.argv[1]:
        case 'cosine_similarity':
            file1, file2 = sys.argv[-2:]
            fields = sys.argv[2:-2]
            cond = lambda x: True
            if fields[-1][:8] == '-filter=':
                patt = parse_pattern(fields[-1][8:])
                cond = lambda x: match_wordline(patt, x)
                fields = fields[:-1]
            with open(file1) as lines1:
                stats1 = wordline_statistics(fields, filter(cond, read_wordlines(lines1)))
            with open(file2) as lines2:
                stats2 = wordline_statistics(fields, filter(cond, read_wordlines(lines2)))
            print(cosine_similarity(stats1, stats2))
        case 'help':
            print_help_message()
        case command:
            search_id = sys.argv[2] if len(sys.argv) > 2 else None
            execute_pipe_on_strings(sys.argv[1], search_id, sys.stdin)
            

