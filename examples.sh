echo "## make sure FILE.conllu is a CoNLLU file or a link to one"

echo "## statistics on POS DEPREL pairs"
cat FILE.conllu | ./deptreepy.py 'statistics POS DEPREL'

echo "## statistics on POS of nsubj"
cat FILE.conllu | ./deptreepy.py 'match_wordlines DEPREL nsubj | statistics POS'

echo "## statistics of POS 3-grams"
cat FILE.conllu | ./deptreepy.py 'ngram_statistics 3 POS'

echo "## statistics of FORM 3-grams ignoring punctuation"
cat FILE.conllu | ./deptreepy.py 'match_wordlines (NOT (POS PUNCT)) | ngram_statistics 3 FORM'

echo "##statistics of tree configurations in terms of POS+DEPREL"
cat FILE.conllu | ./deptreepy.py 'treetype_statistics POS DEPREL'

echo "## cosine similarity of LEMMA for files ENG.conllu and FIN.conllu"
./deptreepy.py cosine_similarity FEATS ENG.conllu FIN.conllu 

echo "## cosine similarity of LEMMA, ignoring words whose POS is PUNCT"
./deptreepy.py cosine_similarity LEMMA -filter='NOT (POS PUNCT)' ENG.conllu FIN.conllu 

echo "## sentences where lemma politi* occurs"
cat FILE.conllu | ./deptreepy.py 'match_trees SEQUENCE_ (LEMMA politi*) | extract_sentences'

echo "## trees where the subsequence be + a/an occurs"
cat FILE.conllu | ./deptreepy.py 'match_trees SUBSEQUENCE (LEMMA be) (LEMMA a)'

echo "trees with a metadata field whose value starts with Wh"
cat FILE.conllu | ./deptreepy.py 'match_trees METADATA *=?Wh*'

echo "## subtrees with both head-initial and head-final modifiers"
cat FILE.conllu | ./deptreepy.py 'match_subtrees TREE (AND) (HEAD_DISTANCE >0) (HEAD_DISTANCE <0)'

echo "## subtrees where the head is a noun and it has no determiner" 
cat FILE.conllu | ./deptreepy.py 'match_subtrees (AND (POS NOUN) (HAS_NO_SUBTREE (DEPREL det)))'

echo "## wordlines with feature starting In"
cat FILE.conllu | ./deptreepy.py 'match_wordlines FEATS *=In*'

echo "## wordlines whose part of speech is not one of a function word"
cat FILE.conllu | ./deptreepy.py 'match_wordlines NOT (POS IN ADP AUX PRON DET *CONJ PUNCT)'

echo "## show trees that contain any ccomp subtree with mark other than 'that'"
cat FILE.conllu | ./deptreepy.py 'match_found_in_tree (TREE_ (DEPREL ccomp) (AND (DEPREL mark) (NOT (LEMMA that))))'

echo "## wordlins excluding a list of stopwords saved in a script file"
cat FILE.conllu | ./deptreepy.py 'from_script stopwords.oper'

echo "## any segment followed by one where the subject is a pronoun"
cat FILE.conllu | ./deptreepy.py 'match_segments SEGMENT (AND) (HAS_SUBTREE (AND (DEPREL nsubj) (POS PRON)))'

echo "## segments of 6 or more past tense sentences"
cat FILE.conllu | ./deptreepy.py 'match_segments (REPEAT >6 (FEATS *=Past*)) | trees2conllu'

echo "## change the to that in all wordlines"
cat FILE.conllu | ./deptreepy.py 'change_wordlines AND (LEMMA the that) (FORM the that)'

echo "## summarize sentences by dropping words below depth 2"
cat FILE.conllu | ./deptreepy.py 'change_trees PRUNE 2 | extract_sentences'

echo "## drop words below depth 2 and return valid CoNLLU stanzas"
cat FILE.conllu | ./deptreepy.py 'change_trees PRUNE 2 | trees2conllu'

echo "## find paths with a noun modified by an nmod:poss modified by an nmod:poss"
cat FILE.conllu | ./deptreepy.py 'find_paths (POS NOUN) (DEPREL nmod:poss) (DEPREL nmod:poss)'

echo "## find partial subtrees where a noun has an adjective and a possessive modifier"
cat FILE.conllu | ./deptreepy.py 'find_partial_subtrees (POS NOUN) (POS ADJ) (DEPREL nmod:poss)'

echo "## extract predicate frames by reading a pattern from a script" 
cat FILE.conllu | ./deptreepy.py 'from_script predicates.oper'

echo "## parse a German text file and analyse the result"
cat FILE.txt | ./deptreepy.py 'txt2conllu Ger | conllu2trees | match_subtrees (POS ADJ)'

echo "## visualize trees in SVG"
cat FILE.conllu | ./deptreepy.py 'visualize_conllu' >FILE-trees.html

echo "## visualize the results of pattern matching"
cat FILE.conllu | ./deptreepy.py 'match_trees (POS NOUN) | trees2conllu | visualize_conllu' >FILE-trees.html

