echo "## building the indexes for the example corpus"
python3 depsearch.py --command build_indexes --corpus example_corpus

echo "## subtrees where the head is a noun and it has no determiner"
python3 depsearch.py --command search --corpus example_corpus --query 'match_subtrees (AND (POS NOUN) (HAS_NO_SUBTREE (DEPREL det)))' --suspend-intermediate-output

echo "## trees where the subsequence be + a/an occurs"
python3 depsearch.py --command search --corpus example_corpus --query 'match_trees SUBSEQUENCE (LEMMA be) (LEMMA a)' --suspend-intermediate-output

echo "## sentences where lemma politi* occurs"
python3 depsearch.py --command search --corpus example_corpus --query 'match_trees SEQUENCE_ (LEMMA politi*) | extract_sentences' --suspend-intermediate-output

echo "## show trees that contain any ccomp subtree with mark other than 'that'"
python3 depsearch.py --command search --corpus example_corpus --query 'match_found_in_tree (TREE_ (DEPREL ccomp) (AND (DEPREL mark) (NOT (LEMMA that))))' --suspend-intermediate-output