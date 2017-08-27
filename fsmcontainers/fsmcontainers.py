# Goals:
#   Consistent, pythonic interface
#   Choice of backends
#   Cache common expensive properties
#   SHARE FSTs whenever possible to cut memory usage, don't copy or mutate FST
#       when there's an alternative
#   Be safe, avoid unexpected mutations.

import functools
import operator
import six
import pynini
from .pynini_utils import PyniniWrapper
import pywrapfst

class FsmContainer(PyniniWrapper):
    """ A base class providing magic methods, and higher-order functions for
    creating magic methods, that are shared by FsmMap and FsmSet.
    """

    def __len__(self):
        try:
            a = self.fst.paths()
        except pywrapfst.FstArgError:
            return float('inf')
        return len(list(a))

    def __bool__(self):
        return not self.lenCompare(0, operator.eq)

    def lenCompare(self, n, op=operator.eq):
            # __len__ can be expensive, but for the common case of
            # comparing  __len__ to a small integer
            # there is a cheap shortcut.
        numPathsToTryFor = n + 1
        try:
            p = pynini.shortestpath(self.fst, nshortest=numPathsToTryFor).paths()
            numPathsFound = len(list(p))
        except pywrap.FstArgError:
            # Signals a cyclic FST with infinite length, which
            # can't equal any finite integer -- so False regardless of n.
            return False
        if op(numPathsFound, n):
            return True
        return False

    def __hash__(self):
        return hash(self.fst.write_to_string() + 
                    str(self.keySerializer).encode() +
                    str(self.valueSerializer).encode())

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            raise TypeError
        if self.keySerializer != other.keySerializer:
            raise ValueError
        if self.valueSerializer != other.valueSerializer:
            raise ValueError
        em = pynini.EncodeMapper("standard", True, True)
        return pynini.equivalent(pynini.encode(self.fst, em).optimize(), 
                                 pynini.encode(other.fst, em).optimize())

    def __contains__(self, key):
        key = FsmSet({key})
        if key.keySerializer != self.keySerializer:
            raise TypeError
        product = key * self
        if product.isEmpty():
            return False
        return True

    @classmethod
    def _binary_op(cls, function):
        """ wrap a pynini two-argument constructive function as a binary
        operation.
        """
        def innerFunction(self, other):
            if not type(other) == type(self):
                raise TypeError
            if self.keySerializer != other.keySerializer:
                raise ValueError
            if self.valueSerializer != other.valueSerializer:
                raise ValueError
            return type(self).fromFst(
                    fst=function(self.fst, other.fst).optimize(),
                    keySerializer=self.keySerializer,
                    valueSerializer=other.valueSerializer)
        return innerFunction

    @classmethod
    def _product_op(cls, function, rightHanded="True"):
        """ wrap a pynini two-argument constructive function as a binary
        operation.
        """
        def innerFunction(self, other):
            if not isinstance(other, FsmContainer):
                raise TypeError
            if self.valueSerializer != other.keySerializer:
                raise ValueError
            if rightHanded:
                fst = function(other.fst, self.fst)
            else:
                fst = function(self.fst, other.fst)
            return type(self).fromFst(fst=fst.optimize(),
                               keySerializer=self.keySerializer, 
                               valueSerializer=other.valueSerializer)
        return innerFunction



@functools.total_ordering
class FsmSet(FsmContainer):
    """ An immutable set backed by a finite state acceptor, implementing all
    Python set operations plus the FSM operations of closure, sigma, sigmaStar,
    concatenation (+), and composition (*) or lenient composition (%) with an
    FsmMap.
    """

#   Many operations are implemented indirectly:
#
#    - closure, sigma, and sigmaStar are inherited from PyniniWrapper.
#
#    - __bool__, __contains__, __hash__, and __len__ are inherited from
#      FsmContainer.
#
#    - functools.total_ordering takes care of comparison operators beyond
#      __ge__ (implemented here) and __eq__ (inherited from FsmContainer).
#
#    - FsmContainer._binary_op and FsmContainer._product_op are used to
#      produce magic methods for other binary operators.

    def __init__(self, *args, **kwargs):
        """ Construct an FsmSet from any combination of arguments accepted
        by the builtin set() constructor. 
        """
        if len(args) == 1 and isinstance(args[0], FsmSet):
            return args[0].copy()
        as_set = set(*args, **kwargs)
        a = FsmSet.fromPairs((i, i) for i in as_set)
        self.fst = a.fst
        self.keySerializer = a.keySerializer
        self.valueSerializer = a.valueSerializer

    def unwrap(self):
        """ From an FsmSet with one element, return that element.
        """
        if self.isScalar():
            out, _, _ = next(self.fst.paths(input_token_type="symbol",
                                            output_token_type="symbol"))
            return self.keySerializer.unpack(out)
        else:
            raise ValueError("Cannot unwrap a set that contains more than"
                             "one item.")

    def __iter__(self, limit=None):
        return self.paths(limit=limit, side="key")

    def __repr__(self):
        exampleItems = list(self.paths(limit=4, side="key"))
        exampleString = ", ".join("'%s'" % i for i in
                sorted(exampleItems)[0:3])
        if len(exampleItems) > 3:
            return "FsmSet({%s, ... })" % exampleString
        return "FsmSet({%s})" % exampleString

    __add__ = FsmContainer._binary_op(pynini.concat)
    __and__ = FsmContainer._binary_op(pynini.intersect)
    __or__  = FsmContainer._binary_op(pynini.union)
    __sub__ = FsmContainer._binary_op(pynini.difference)
    __xor__ = FsmContainer._binary_op(
                lambda self, other: (self | other) - (self & other))
    __mul__ = FsmContainer._product_op(pynini.compose)
    if six.PY3:
        __matmul__ = FsmContainer._product_op(pynini.leniently_compose)


    def __ge__(self, other):
        if not isinstance(other, FsmSet):
            raise TypeError
        if self.keySerializer != other.keySerializer:
            raise ValueError
        if (self - other) and not (other - self):
            return True
        return False


class FsmMap(FsmContainer):
    """ An immutable multimapping backed by a finite state transducer. If
    a key corresponds to multiple values, subscripting gives the shortest value
    if the transducer is unweighted, or the one with greatest weight if the
    transducer is weighted. To get more values, use FsmMap.all or
    FsmMap.only(n) with n>1. Implements all Python map operations plus
    closure, projection, sigma, sigmaStar, concatenation (+), composition (*),
    lenient composition (%), inversion (~ or .inv), and union (|). """

#   Many operations are implemented indirectly:
#
#    - closure, sigma, and sigmaStar are inherited from PyniniWrapper.
#
#    - __bool__, __contains__, __hash__, and __len__ are inherited from
#      FsmContainer.
#
#    - FsmContainer._binary_op and FsmContainer._product_op are used to
#      produce magic methods for all binary operators.

    __projection_class__ = FsmSet

    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            if isinstance(args[0], dict):
                pairs = list(args[0].items())
            else:
                pairs = list(args[0])
        else:
            pairs = [()]
        pairs += list(kwargs.items())
        a = FsmMap.fromPairs(pairs)
        self.fst = a.fst
        self.keySerializer = a.keySerializer
        self.valueSerializer = a.valueSerializer

    @property
    def inv(self):
        return self.__invert__()

    def __invert__(self):
        return type(self).fromFst(fst=pynini.invert(self.fst),
                                  keySerializer=self.valueSerializer,
                                  valueSerializer=self.keySerializer)

    def __getitem__(self, key):
        if isinstance(key, six.string_types):
            key = FsmSet({key})
        elif not isinstance(key, FsmSet):
            key = FsmSet(key)

        try:
            limit = getattr(self, "limit")
        except AttributeError:
            limit = 1

        if not self.keySerializer == key.valueSerializer:
            raise ValueError

        try:
            form = (key * self).paths(limit=limit, side="value")
        except StopIteration:
            raise KeyError

        if limit == 1:
            return next(form)
        else:
            return FsmSet(form)

    def __iter__(self, limit=None):
        return self.paths(limit=limit, side="key")

    keys = __iter__

    def values(self, limit=None):
        return self.paths(limit=limit, side="value")

    def items(self, limit=None):
        return self.paths(limit=limit, side="both")

    @property
    def all(self):
        out = self.copy()
        out.limit = None
        return out

    def only(self, n):
        out = self.copy()
        out.limit = n
        return out

    def __repr__(self):
        exampleItems = list(self.paths(limit=4, side="both"))
        exampleString = ", ".join("'%s': '%s'" % (k,v) for k,v in
                sorted(exampleItems)[0:3])
        if len(exampleItems) > 3:
            exampleString += " ... "
        return "FsmMap({%s})" % exampleString

    __add__ = FsmContainer._binary_op(pynini.concat)
    __or__  = FsmContainer._binary_op(pynini.union)
    __mul__ = FsmContainer._product_op(pynini.compose)
    if six.PY3:
        __matmul__ = FsmContainer._product_op(pynini.leniently_compose)


