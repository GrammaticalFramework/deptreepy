# Depsesarch

Multistage search system for large corpora annotated with Universal Dependencies

## Installing the software and dependencies

Since the repository contains a submodule, it should be cloned to local using:

```
git clone --recurse-submodules https://github.com/GrammaticalFramework/deptreepy.git
# or, with SSH:
git clone --recurse-submodules git@github.com:GrammaticalFramework/deptreepy.git
# or, if already cloned:
git submodule update --init --recursive
```

Depsearch requires Python3 at least version 3.10, but version 3.11 or higher is recommended. To install dependencies, you can run
```
pip install -r requirements.txt
```

## Operation

After having the required dependencies, Depsearch can be used with the command
```
python3 depsearch.py --command <command> --corpus <corpus> <other_flags>
```

To get help on available flags, run
```
python3 depsesarch.py --help
```

## Requirements for input corpus file

The system takes in CoNLLU annotated corpus, which should be in .csv format. The file should be located in the ```corpora``` folder in the root directory (which is the same directory as of the depsearch.py file).

The CoNLLU annotated corpus should have comments starting with one single hash (#). Wordlines form sentence blocks, where blocks are separated by one empty line. The file should not include any block that consists of only invalid tokens (incl. comment lines and multi-word token lines). A preprocessing code for corpora (```./depsearch_tools/reformat_corpus.py```) is provided to handle some of the common issues. The code can be run by the following syntax.

```
python3 ./depsearch_tools/reformat_corpus.py \path\to\original\corpus.csv \path\to\output\formatted\corpus.csv
```

### Building indexes

Before searching with depsearch, the indexes must be built. The corpus is expected to be found in the ```corpora``` folder under the 
root folder. The desired format is CoNLL-U but with ```.csv``` suffix. For example, to build the indexes using the 
```example_corpus.csv``` file, you can run:
```
python3 depsearch.py --command build_indexes --corpus example_corpus
```

The corpus name is included in the command without the suffix.

There is also a ```number-of-subcorpora``` flag for determining the number of sub-corpora which the corpus will be 
split into during pre-search

### Searching

After having the indexes, you can start searching. The command to search is
```
python3 depsearch.py --command search --corpus <corpus> --query <query>
```

The 10 fields for composing a queries (as in CoNLL-U format) are ```ID```, ```FORM```, ```LEMMA```, ```POS```, ```XPOS```, 
```FEATS```, ```HEAD```, ```DEPREL```, ```DEPS```, ```MISC```. However, only the 6 fields ```FORM```, ```LEMMA```, ```POS```,
```XPOS```, ```FEATS```, ```DEPREL``` are handled by the pre-search system. The other fields can be typed in as usual, but 
their corresponding parts in the query will be neglected in the pre-search system.

Depsearch accepts the query syntax as the command of deptreepy. See here for reference: https://github.com/GrammaticalFramework/deptreepy.

The pre-search systems handle only deptreepy's search commands, i.e. one of the followings: ```match_trees```, ```match_subtrees```, 
```match_found_in_tree```, ```match_wordlines```, ```find_partial_subtrees```, ```find_paths```. Other commands can be inputted
to the integrated system as usual, but those are neglected in the pre-search.

Patterns not starting with a field name, ```AND```, ```OR```, ```NOT```, ```SEQUENCE```, ```SEQUENCE_```, ```SUBSEQUENCE```, 
```TREE```, or ```TREE_``` are also neglected in the pre-search. For patterns starting with ```TREE``` or ```TREE```, only 
the root's pattern is taken into pre-search.

For multi-stage queries in deptreepy (separated by ```|```), only the first stage is handled by the pre-search system.

There is also the flag ```--suspend-intermediate-output``` for hiding the output of the pre-search process.

Details about the flag handled by Depsearch can be viewed using the command
```python3 depsearch.py --help```.

Some example commands can be found in ```depsearch_tools/example_commands.sh```.

## Context retrieval and including context in search result.

The system supports retrieving contexts (sentences surrounding a search result). Currently, context retrieval is available for queries composed using the commands ```match_trees```, ```match_subtrees```, and 
```match_found_in_tree```. 

To include the context in the result, use the flag ```--context-size``` followed by an integer indicating the number of sentences included before and after the search match.

## Interface

The system comes with a web interface. To set up the interface, run the following command in the root folder:
```
uvicorn depsearch_interface:app --host 0.0.0.0 --port 8000
```

After completing setting up, the interface should be available at localhost port 8000, i.e. http://localhost:8000.

## Limitations

There are some limitations acknowledged regarding the query, which is due to the compatibility of the two search systems used.

- **Queries containing logical expressions (AND, OR, NOT) which cannot be expressed by not using parentheses without ambiguity 
or those can be expressed as such but contains both AND and OR operations in its final form.** <br>
This is limited by the token expression rules in the pre-search system. Hence, those are neglected in the pre-search system.
- **Queries containing logical expressions (AND, OR, NOT) which having only negated literals (NOT) in its final form (expressed 
without using parentheses).** <br>
This is limited by the token expression rules in the pre-search system. Hence, those are neglected in the pre-search system.
