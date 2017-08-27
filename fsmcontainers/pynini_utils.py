#pylint: disable=bad-whitespace
""" This module contains a wrapper class and utility functions for working with
Pynini FSMs. It gives the illusion of seamless FSM creation and manipulation
using any object for which we have a serialization protocol in the
`serializers` module. 
"""

import collections
import six
import pynini
import pywrapfst
from .serializers import Serializer

class PyniniWrapper(object):
    """ Base class implementing serialization and conversion to/from bytes for
    Pynini FSMs.
    """

    __projection_class__ = None

    def __init__(self, *args, **kwargs):
        """ __init__ must be implemented by subclasses. """
        return NotImplemented

    @classmethod
    def fromPairs(cls, pairs):
        """ Class method to be invoked on subclasses. Create a member of the
        appropriate subclass from a list of pairs, where the first element of
        each pair is a string from the top side of a transducer and the second
        element is a string from the bottom side. Subclasses that implement
        acceptors rather than transducers should redefine fromPairs to either
        raise an error or drop the second element of each pair."""
        self = cls.__new__(cls)
        pairs = list(pairs)
        kproto, vproto = pairs[0] if pairs else ("", "")
        self.keySerializer = Serializer.from_prototype(kproto)
        self.valueSerializer = Serializer.from_prototype(vproto)
        pairs = [self.serializePair(pair) for pair in pairs]
        self.fst = pynini.string_map(pairs, 
                                     input_token_type="utf8",
                                     output_token_type="utf8")
        return self

    def serializePair(self, pair):
        """ Run both elements of a pair through the correct serializer. """
        return (self.keySerializer.serialize(pair[0]), 
                self.valueSerializer.serialize(pair[1]))

    @classmethod
    def fromFst(cls, fst, keySerializer=None, valueSerializer=None):
        """ Create a member of the appropriate subclass from an FSM and,
        optionally, one or two Serializer objects. """
        self = cls.__new__(cls)
        self.fst = fst
        self.keySerializer = keySerializer or Serializer.from_prototype("")
        self.valueSerializer = valueSerializer or Serializer.from_prototype("")
        return self

    @property
    def sigma(self):
        """ Assemble an acceptor of the appropriate subclass which accepts
        every symbol that occurs in my symbol table.
        """
        sigma = set()
        cls = type(self).__projection_class__ or type(self)
        isyms = self.fst.input_symbols()
        osyms = self.fst.output_symbols()
        for state in self.fst.states():
            for arc in self.fst.arcs(state):
                sigma |= {pynini_decode(isyms.find(arc.ilabel))}
                sigma |= {pynini_decode(osyms.find(arc.olabel))}
        return cls(sigma)

    @property
    def sigmaStar(self):
        """ Assemble an infinite acceptor which accepts the closure of sigma.
        This is useful in handling context-dependent rewrite rules.
        """
        return self.sigma.closure()

    def closure(self):
        """ Construct a transducer or acceptor of the appropriate subclass
        which is a closure of my FSM.
        """
        cls = type(self)
        return cls.fromFst(fst=pynini.closure(self.fst).optimize(),
                           keySerializer=self.keySerializer,
                           valueSerializer=self.valueSerializer)

    def project(self, side="key"):
        if side not in {"key", "value"}:
            raise ValueError

        cls = type(self).__projection_class__ or type(self)
        project_output = (side == "value")
        if side == "key":
            codec = self.keySerializer
        else:
            codec = self.valueSerializer

        return cls.fromFst(
                fst=self.fst.copy().project(project_output=project_output), 
                keySerializer=codec, 
                valueSerializer=codec)

    def copy(self):
        cls = type(self)
        out = cls.__new__(cls)
        for k, v in self.__dict__.items():
            setattr(out, k, v)
        return out

    def paths(self, limit=None, side=None):
        """ Attempt to return an iterator over keys in this FsmContainer.

        If an FsmContainer is cyclic (infinite), a limit must be specified,
        since Pynini refuses to construct infinite iterators.

        TODO: find a workaround for this.
        """

        if limit is None:
            try:
                stringpaths = self.fst.paths(
                    input_token_type='symbol',
                    output_token_type='symbol')
            except pywrapfst.FstArgError:
                print("Can't iterate over this mapping. It is cyclic and may accept infinitely many keys.")
                raise
        else:
            stringpaths = pynini.shortestpath(self.fst, nshortest=limit).paths(
                input_token_type='symbol',
                output_token_type='symbol')
        if side=="key":
            for stringpath in stringpaths:
                yield self.keySerializer.inflate(pynini_decode(stringpath[0]))
        elif side=="value":
            for stringpath in stringpaths:
                yield self.keySerializer.inflate(pynini_decode(stringpath[1]))
        else:
            for stringpath in stringpaths:
                yield (self.keySerializer.inflate(pynini_decode(stringpath[0])),
                       self.keySerializer.inflate(pynini_decode(stringpath[1])))


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

def pynini_find_nonfunctional(fst, strictness=100):
    """ Allauzen and Mohri: an FST f is functional (i.e. one-to-one or
    many-to-one) iff f' .o. f is the identity function over f's domain.
    Rather than implement A&Z's algorithm to determine strict identity,
    we test identity for a random sample of paths.
    """
    fpcf = fst.copy().invert()*fst
    for top, bottom, _ in pynini.randgen(fpcf,
                                         npath=strictness,
                                         max_length=strictness)\
                                .paths(input_token_type="symbol",
                                       output_token_type="symbol"):
        if top != bottom:
            return (clean(top), clean(bottom))
    return False

