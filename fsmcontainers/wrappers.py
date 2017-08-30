#pylint: disable=bad-whitespace

# TODO: top/bottom rather than key/value terminology

import collections
import six
import pynini
import pywrapfst
from .serializers import Serializer

NotImplemented = False

class EngineWrapper(object):
    def __init__(self, contents):
        return NotImplemented

    def __eq__(self, other):
        return NotImplemented

    def accepts(self, item, side="top"):
        return NotImplemented

    def apply(self, item, direction="down"):
        return NotImplemented

    def pathIterator(self, limit=None, side=None):
        return NotImplemented

    def concatenate(self, other):
        return NotImplemented

    def union(self, other):
        return NotImplemented

    def priorityUnion(self, other):
        return NotImplemented

    def intersect(self, other):
        return NotImplemented

    def subtract(self, other):
        return NotImplemented

    def compose(self, other):
        return NotImplemented

    def lenientlyCompose(self, other):
        return NotImplemented

    def project(self, other, side):
        return NotImplemented

    def star(self):
        return NotImplemented

    def plus(self):
        return NotImplemented

    def sigma(self):
        return NotImplemented

    def makeRewrite(self, 
                    leftEnvironment=None, rightEnvironment=None,
                    leftBottomTape=False, rightBottomTape=False):
        return NotImplemented

    def findAmbiguity(self, strictness):
        return NotImplemented


def _constructiveOp(op):
    def innerFunction(self, other):
        cls = type(self)
        return cls(op(self.fsm, other.fsm))
    return innerFunction

class PyniniWrapper(EngineWrapper):
    def __init__(self, fsm):
        self.fsm = fsm

    @classmethod
    def fromPairs(cls, pairs):
        fsm = pynini.string_map(
                cls.encodePairs(pairs), 
                input_token_type="utf8",
                output_token_type="utf8")
        return cls(fsm)

    @classmethod
    def encodePairs(cls, pairs):
        for k, v in pairs:
            if "\x00" in k or "\x00" in v:
                raise ValueError
            yield (k, v)

    @classmethod
    def fromItems(cls, items):
        pairs = cls.encodePairs(zip(items, items))
        return cls.fromPairs(pairs)

    @classmethod
    def fromItem(cls, item):
        pairs = cls.encodePairs([(item, item)])
        return cls.fromPairs(pairs)

    def __eq__(self, other):
        em = pynini.EncodeMapper("standard", True, True)
        return pynini.equivalent(pynini.encode(self.fsm, em).optimize(), 
                                 pynini.encode(other.fsm, em).optimize())

    def accepts(self, item, side="top"):
        cls = type(self)
        wrappedItem = cls.fromPairs([(item, item)])
        if side == "top":
            product = wrappedItem.compose(self)
        else:
            product = self.compose(wrappedItem)
        paths = product.pathIterator(limit=1)
        return len(list(paths)) == 1

    def pathIterator(self, limit=None, side=None):
        if limit is None:
            try:
                stringpaths = self.fsm.paths(
                    input_token_type='symbol',
                    output_token_type='symbol')
            except pywrapfst.FstArgError:
                print("Can't iterate over this mapping. It is cyclic and may accept infinitely many keys.")
                raise
        else:
            stringpaths = pynini.shortestpath(self.fsm, nshortest=limit).paths(
                input_token_type='symbol',
                output_token_type='symbol')
        if side=="key":
            for stringpath in stringpaths:
                yield pynini_decode(stringpath[0])
        elif side=="value":
            for stringpath in stringpaths:
                yield pynini_decode(stringpath[1])
        else:
            for stringpath in stringpaths:
                yield (pynini_decode(stringpath[0]),
                       pynini_decode(stringpath[1]))

    concatenate = _constructiveOp(pynini.concat)
    union = _constructiveOp(pynini.union)
    priorityUnion = _constructiveOp(...)

    def intersect(self, other):
        self.fsm.optimize() # Pynini intersection will fail on unoptimized FSAs
        return _constructiveOp(pynini.intersect)(self, other)

    subtract = _constructiveOp(pynini.difference)
    compose = _constructiveOp(pynini.compose)
    lenientlyCompose = _constructiveOp(pynini.leniently_compose)

    def project(self, side="key"):
        if side not in {"key", "value"}:
            raise ValueError
        tf = (side == "value")
        cls = type(self)
        return cls(self.fsm.copy().project(project_output=tf))

    def star(self):
        cls = type(self)
        return cls(pynini.closure(self.fsm).optimize())

    def plus(self):
        cls = type(self)
        return cls(pynini.closure(self.fsm, 1).optimize()) #TEST THIS

    def sigma(self):
        sigma = set()
        isyms = self.fsm.input_symbols()
        osyms = self.fsm.output_symbols()
        for state in self.fsm.states():
            for arc in self.fsm.arcs(state):
                sigma |= {pynini_decode(isyms.find(arc.ilabel))}
                sigma |= {pynini_decode(osyms.find(arc.olabel))}
        cls = type(self)
        return cls((s,s) for s in sigma)

    def findAmbiguity(self, strictness=100):
        """ Allauzen and Mohri: an FST f is functional (i.e. one-to-one or
        many-to-one) iff f' .o. f is the identity function over f's domain.
        Rather than implement A&Z's algorithm to determine strict identity,
        we test identity for a random sample of paths.
        """
        fpcf = self.fsm.copy().invert() * self.fsm
        for top, bottom, _ in pynini.randgen(fpcf,
                                             npath=strictness,
                                             max_length=strictness)\
                                    .paths(input_token_type="symbol",
                                           output_token_type="symbol"):
            if top != bottom:
                return (clean(top), clean(bottom))
        return None


def pynini_decode(inputBytes):
    """ Pynini often outputs bytestrings with unprintable characters
    represented in an unusual way. Run them through this to get plain unicode.
    """
    asString = inputBytes.decode("utf8")
    asTokens = (from_att_symbol(symbol) for symbol in asString.split(' '))
    return "".join(asTokens)

def from_att_symbol(string):
    """ OpenFST outputs symbol table representations in an awkward
    format. Attempt to deal with that gracefully. """
    # pylint: disable=too-many-return-statements
    if string.startswith("<0"):
        return six.unichr(int(string.strip('<>'), 16))
    if string.startswith("<") and string.endswith(">"):
        return {
            "NUL": chr(0),  "":    chr(0),  "epsilon": chr(0),
            "SOH": chr(1),  "STX": chr(2),  "ETX": chr(3),  "EOT": chr(4),
            "ENQ": chr(5),  "ACK": chr(6),  "BEL": chr(7),  "BS":  chr(8),
            "HT":  chr(9),  "LF":  chr(10), "VT":  chr(11), "FF":  chr(12),
            "CR":  chr(13), "SO":  chr(14), "SI":  chr(15), "DLE": chr(16),
            "DC1": chr(17), "DC2": chr(18), "DC3": chr(19), "DC4": chr(20),
            "NAK": chr(21), "SYN": chr(22), "ETB": chr(23), "CAN": chr(24),
            "EM":  chr(25), "SUB": chr(26), "ESC": chr(27), "FS":  chr(28),
            "GS":  chr(29), "RS":  chr(30), "US":  chr(31), "SPACE": chr(32),
            "DEL": chr(127)
        }[string.strip('<>')]
    if len(string) > 1:
        return "[" + string + "]"
    if string == "[":
        return "\\["
    if string == "]":
        return "\\]"
    if string == "\\":
        return "\\\\"
    return string


