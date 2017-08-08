#pylint: disable=bad-whitespace
""" Utility functions for working with Pynini FSTs. Pynini can produce Unicode
FSTs, but by default it produces ones where the symbols are bytes objects, and
represents unprintable bytes and special symbols as strings like
:literal:`"<epsilon>"`, :literal:`"<0xef>"`, or :literal:`"<SPACE>"`. Using
these utility functions rather than Pynini builtin functions to construct and
apply FSTs helps ensure that Unicode input is handled properly.
"""

import collections
import six
import pynini
import pywrapfst
EM = pynini.EncodeMapper("standard", True, True)

def a(s):           #pylint: disable=invalid-name
    """Create a unicode acceptor from a string."""
    return pynini.acceptor(s, token_type="utf8")

def t(s1, s2):      #pylint: disable=invalid-name
    """Create a unicode transducer from two strings."""
    return pynini.transducer(a(s1), a(s2))

def m(l):           #pylint: disable=invalid-name
    """Create a unicode acceptor or transducer from a list of (str, str)
    pairs."""
    return pynini.string_map(l, input_token_type="utf8",
                             output_token_type="utf8")

def u(*args):       #pylint: disable=invalid-name
    """Take the union of many acceptors or transducers, or of a single
    iterable of acceptors or transducers."""
    if len(args) == 1 and isinstance(args[0], collections.Iterable):
        return pynini.union(*args[0])
    return pynini.union(*args)

def apply_down(transducer, string, *args, **kwargs):
    """Mimics xfst/foma-style apply down.

    Args:
        transducer: A finite state transducer.
        string: A string to apply at the top side of `transducer`.

    Returns:
        Set[str]: A set of strings that can be read off the bottom side of
        `transducer` when applying `string` at the top side.
    """
    return set(lower_words(a(string)*transducer), *args, **kwargs)

def apply_up(transducer, string, *args, **kwargs):
    """Mimics xfst/foma-style apply up.

    Args:
        transducer: A finite state transducer.
        string: A string to apply at the bottom side of `transducer`.

    Returns:
        Set[str]: A set of strings that can be read off the top side of
        `transducer` when applying `string` at the bottom side.
    """
    return set(upper_words(transducer*a(string)), *args, **kwargs)

def words(transducer, side="top", limit=None):
    if side in ["top", "bottom"]:
        encode = lambda t: t.copy().project(project_output=(side=="bottom"))
        decode = lambda t: t
        cleanup = lambda top, bottom, weight: clean(top)
    elif side == "both":
        encode = lambda t: t.copy().encode(EM)
        decode = lambda t: t.decode(EM)
        cleanup = lambda top, bottom, weight: (clean(top), clean(bottom))
    else:
        raise ValueError("Side must be one of 'top', 'bottom', or 'both'.")

    try:
        paths = transducer.paths(input_token_type="symbol",
                                 output_token_type="symbol")
    except pywrapfst.FstArgError:
        if limit:
            transducer = encode(transducer).optimize()
            transducer = pynini.shortestpath(transducer,
                                             nshortest=limit,
                                             unique=True)
            paths = decode(transducer.paths(input_token_type="symbol",
                                            output_token_type="symbol"))
        else:
            raise ValueError("You must specify a value of nshortest when calling words() on a cyclic FST.")

    for path in paths:
        yield cleanup(*path)


def upper_words(transducer, *args, **kwargs):
    """ Get the words read by the upper side of `transducer`"""
    return words(transducer, side="top", *args, **kwargs)

def lower_words(transducer, *args, **kwargs):
    """ Get the words read by the lower side of `transducer`"""
    return words(transducer, side="bottom", *args, **kwargs)

def get_sigma(stbl):
    """ Given a symbol table from an FST, convert it to a list of strings that
    can be fed to string_map. """
    sigma_list = []
    for _, symbol in pynini.SymbolTableIterator(stbl):
        symbol = clean(symbol)
        sigma_list.append((symbol, symbol))
    return sigma_list

def clean(string):
    """ Pynini often outputs bytestrings with unprintable characters
    represented in an unusual way. Run them through this to get plain unicode.
    """
    return from_att_word(string.decode("utf8"))

def from_att_symbol(string):
    """ OpenFST outputs symbol table representations in an awkward
    format. Attempt to deal with that gracefully. """
    # pylint: disable=too-many-return-statements
    if string.startswith("<0"):
        return six.unichr(int(string.strip('<>'), 16))
    if string.startswith("<"):
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

def from_att_word(string):
    """ Decode a string of characters in OpenFST's output format. """
    return "".join(from_att_symbol(token) for token in string.split())

def find_nonfunctional(fst, strictness=100):
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
