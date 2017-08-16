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

def encode(string):
    return string

def decode(string):
    """ Pynini often outputs bytestrings with unprintable characters
    represented in an unusual way. Run them through this to get plain unicode.
    """
    return from_att_word(string.decode("utf8"))

def from_att_word(string):
    """ Decode a string of characters in OpenFST's output format. """

    return "".join(from_att_symbol(token) for token in string.split(' '))

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

