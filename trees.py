import sys
from dataclasses import dataclass
from typing import Iterable

@dataclass
class WordLine:
    "UD wordlines with 10 named fields"
    ID: str
    FORM: str
    LEMMA: str
    POS: str
    XPOS: str
    FEATS: str
    HEAD: str
    DEPREL: str
    DEPS: str
    MISC: str

    def as_dict(self):
        return {
          'ID': self.ID, 'FORM': self.FORM, 'LEMMA': self.LEMMA,
          'POS': self.POS, 'XPOS': self.XPOS,
          'FEATS': self.FEATS, 'HEAD': self.HEAD, 'DEPREL': self.DEPREL,
          'DEPS': self.DEPS, 'MISC': self.MISC
          }
    
    def __str__(self):
        return '\t'.join(self.as_dict().values())

    def feats(self) -> dict:
        featvals = [fv.split('=') for fv in self.FEATS.split('|')]
        return {fv[0]: fv[1] for fv in featvals}

WORDLINE_FIELDS = set('ID FORM LEMMA POS XPOS FEATS HEAD DEPREL DEPS MISC'.split())

ROOT_LABEL = 'root'

def ifint(id: str) ->int:
    if id.isdigit():
        return int(id)
    else:
        return int(float(id))  # for ids like '7.1'

    
class NotValidWordLine(Exception):
    pass


class NotValidTree(Exception):
    pass


def read_wordline(s: str) -> WordLine:
    "read a string as a WordLine, fail if not valid"
    fields = s.strip().split('\t')
    if len(fields) == 10 and fields[0][0].isdigit():
        return WordLine(*fields)
    else:
        raise NotValidWordLine


def read_wordlines(lines):
    "read a sequence of strings as WordLines, ignoring failed ones"
    for line in lines:
        try:
            word = read_wordline(line)
            yield word
        except:
            pass

        
def ngrams(n, trees):
    "n-grams of wordlines, inside trees but not over tree boundaries"
    for tree in trees:
        wordlines = tree.wordlines()
        for i in range(len(wordlines)-n):
            yield wordlines[i:i+n] 


def wordline_ngrams(n, wordliness):
    "n-grams of wordlines, inside stanzas but not over tree boundaries"
    for wordlines in wordliness:
        for i in range(len(wordlines)-n):
            yield wordlines[i:i+n] 


def replace_by_underscores(fields, wordline):
    "replace the values of named fields by underscores"
    ldict = wordline.as_dict()
    for field in fields:
        ldict[field] = '_'
    return WordLine(**ldict)

    
def wordline_statistics(fields, wordlines):
    "frequency table of a combination of fields, as dictionary"
    stats = {}
    for word in wordlines:
        value = tuple(word.as_dict()[field] for field in fields)
        stats[value] = stats.get(value, 0) + 1
    return stats


def sorted_statistics(stats, key=lambda x: x):
    "frequency given as dict, sorted as list in descending order"
    stats = list(stats.items())
    stats.sort(key = lambda it: -key(it[1]))
    return stats


def cosine_similarity(stats1, stats2):
    "cosine similarity between two frequency dictionaries"
    dot = 0
    for k in stats1:
        dot += stats1[k] * stats2.get(k, 0)
    len1 = sum(v*v for v in stats1.values())
    len2 = sum(v*v for v in stats2.values())
    return dot/((len1 ** 0.5) * (len2 ** 0.5)) 


def wordline_ngram_statistics(fields, wordlinengrams):
    "frequency table of n-grams of field combinations"
    stats = {}
    for ngram in wordlinengrams:
        value = tuple(tuple(word.as_dict()[field] for field in fields) for word in ngram)
        stats[value] = stats.get(value, 0) + 1
    return stats


@dataclass
class Tree:
    "rose trees"
    root: object
    subtrees: list

    def prettyprint(self, level=0, indent=2):
        lines = [level*indent*' ' + str(self.root)]
        level += 1
        for tree in self.subtrees:
            lines.extend(tree.prettyprint(level))
        return lines

    def __len__(self):
        return 1 + sum(map(len, self.subtrees))

    def depth(self):
        if self.subtrees:
            return 1 + max(map(lambda t: t.depth(), self.subtrees))
        else:
            return 1


def prune_subtrees_below(tree: Tree, depth: int) -> Tree:
    "leave out parts of trees below given depth, 1 means keep root only"
    if depth <= 1:
        tree.subtrees = []
    else:
        tree.subtrees = [prune_subtrees_below(st, depth-1) for st in tree.subtrees]
    return tree
    
    
@dataclass
class DepTree(Tree):
    "depencency trees: rose trees with word lines as nodes"
    comments: list[str]
    
    def __str__(self):
        lines = self.comments
        lines.extend(self.prettyprint())
        return '\n'.join(lines)

    def wordlines(self):
        words = [self.root]
        for tree in self.subtrees:
            words.extend(tree.wordlines())
        words.sort(key=lambda w: ifint(w.ID))
        return words

    def sentence(self):
        return ' '.join([word.FORM for word in self.wordlines()])

    def prefix_comments(self, ss):
        self.comments = ss + self.comments

    def add_misc(self, s):
        self.root.MISC += '+' + s
        

    
def build_deptree(ns: list[WordLine]) -> DepTree:
    "build a dependency tree from a list of word lines"
    def build_subtree(ns, root):
        subtrees = [build_subtree(ns, n) for n in ns if n.HEAD == root.ID]
        return DepTree(root, subtrees, [])
                           
    try:
        root = [n for n in ns if n.HEAD == '0'][0]
        dt = build_subtree(ns, root)
#        if len(dt) != len(ns):   # 7.1
#            raise NotValidTree
        return dt
    except:
        raise NotValidTree(str(ns))

    
def relabel_deptree(tree: DepTree) -> DepTree:
    "set DEPREL of head to root and its HEAD to 0, renumber wordlines to 1, 2, ..."
    root = tree.root
    root.MISC = root.MISC + '('+root.DEPREL+')'
    root.DEPREL = 'root'
    words = tree.wordlines()  # sorted by ID
    numbers = {w.ID:  str(i) for w, i in zip(words, range(1, len(words) + 1))}
    numbers[root.HEAD] = '0'

    def renumber(t):
        if t.root.ID.isdigit():
            t.root.ID = numbers[t.root.ID]
        t.root.HEAD = numbers[t.root.HEAD]
        for st in t.subtrees:
            renumber(st)
        return t

    r = renumber(tree)
#    r.prefix_comments(tree.comments)
    return r


def nonprojective(tree: DepTree) -> bool:
    "if a subtree is not projective, i.e. does not span over a continuous sequence"
    ids = [int(w.ID) for w in tree.wordlines() if w.ID.isdigit()]
    ids.sort()
    return len(ids) < 1 + max(ids) - min(ids)

    
def echo_conllu_file(file: Iterable[str]):
    "reads a stream of lines, interprets them as word lines, and prints back" 
    for line in file:
        try:
            t = read_wordline(line)
            print(t)
        except:
            if not line.strip() or line.startswith('#'):
                print(line.strip())
            else:
                print('INVALID', line)


if __name__ == '__main__':
    echo_conllu_file(sys.stdin)

