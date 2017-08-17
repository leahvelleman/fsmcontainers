# Goals:
#   Consistent, pythonic interface
#   Choice of backends
#   Cache common expensive properties
#   SHARE FSTs whenever possible to cut memory usage, don't copy or mutate FST
#       when there's an alternative
#   Be safe, avoid unexpected mutations.
#   
#
#   Ways we need to interact with an FSM:
#       Giving/getting core Python types -- basic API:
#       - Encoding/decoding between unicode strings and its preferred
#           representation
#       - Marshalling/unmarshalling other objects to unicode strings
#       - Constructing from lists of pairs of unmarshalled objects
#       - Getting paths as lists of pairs of unmarshalled objects
#       - __eq__
#
#      Giving/getting FSMContainers:
#       - sigma
#       - __or__, __plus__, __times__
#
#       Giving/getting views on an FSMContainer:
#       - inv, best(n), all, draw(n)
#
#       Giving/getting core Python types using this API:
#       - len() --- using paths()
#       - isEmpty() --- using nshortest() and paths()
#       - Checking membership (using compose() and isEmpty())
#
#       Plus for mappings:
#       - Iterating over keys/values/k-v pairs (using paths())
#       - __getitem__() --- using constructor, compose(), paths()
#
#       Plus for sets:
#       - Intersection, XOR, minus



# pylint: disable=fixme
import functools
import pynini
from . import pynini_utils
import pywrapfst
from .serializers import *

class FsmContainer(object):
    """ Base class for container classes backed by FSTs.

    """

    def __init__(self, *args, **kwargs):
        return NotImplemented

    @classmethod
    def fromPairs(cls, pairs):
        pairs = list(pairs)
        self = cls.__new__(cls)
        if len(pairs) == 0:
            self.keySerializer = self.valueSerializer =\
                    Serializer.from_prototype("")
        else:
            kproto, vproto = pairs[0]
            self.keySerializer = Serializer.from_prototype(kproto)
            self.valueSerializer = Serializer.from_prototype(vproto)
        for pair in pairs:
            pair = (pynini_utils.encode(self.keySerializer.serialize(pair[0])),
                    pynini_utils.encode(self.keySerializer.serialize(pair[1])))
        self.fst = pynini.string_map(pairs, 
                                     input_token_type="utf8",
                                     output_token_type="utf8")
        return self

    @classmethod
    def fromFst(cls, fst, keySerializer=None, valueSerializer=None):
        if not keySerializer:
            keySerializer = Serializer.from_prototype("")
        if not valueSerializer:
            valueSerializer = Serializer.from_prototype("")
        self = cls.__new__(cls)
        self.fst = fst
        self.keySerializer = keySerializer
        self.valueSerializer = valueSerializer
        return self

    # Class methods that subclasses can call on 
    # to wrap Pynini fst operations
    ###########################################

    @classmethod
    def binary_op(cls, function):
        """ Wrap a Pynini two-argument constructive function as a binary
        operation.
        """
        def innerfunction(self, other):
            targetcls = type(self)
            if not type(other) == type(self):
                raise TypeError
            if self.keySerializer != other.keySerializer:
                raise ValueError
            if self.valueSerializer != other.valueSerializer:
                raise ValueError
            return targetcls.fromFst(
                    fst=function(self.fst, other.fst).optimize(),
                    keySerializer=self.keySerializer,
                    valueSerializer=other.valueSerializer)
        return innerfunction

    @classmethod
    def product_op(cls, function):
        """ Wrap a Pynini two-argument constructive function as a binary
        operation.
        """
        def innerfunction(self, other):
            if not isinstance(other, FsmContainer):
                raise TypeError
            if self.valueSerializer != other.keySerializer:
                raise ValueError
            return FsmMap.fromFst(fst=function(self.fst, other.fst).optimize(),
                                  keySerializer=self.keySerializer,
                                  valueSerializer=other.valueSerializer)
        return innerfunction

    # Properties that are available for any FsmContainer
    ####################################################

    def isScalar(self):
        """ Return True if the FsmContainer has exactly one path.
        """
        twoshortest = [p for p in
                       pynini.shortestpath(self.fst, nshortest=2).paths()]
        if len(twoshortest) == 1:
            return True
        return False

    def __hash__(self):
        return hash(self.fst.write_to_string() + 
                    str(self.keySerializer).encode() +
                    str(self.valueSerializer).encode())

    # TODO cache
    @property
    def sigma(self):
        """ Assemble set of symbols.

        If c is an FsmContainer, c.sigma is an FsmSet containing each of the
        symbols that appear in keys or values in c. c.sigma can be used as an
        acceptor matching a single character.
        """
        sigma = set()
        isyms = self.fst.input_symbols()
        osyms = self.fst.output_symbols()
        for state in self.fst.states():
            for arc in self.fst.arcs(state):
                sigma |= {pynini_utils.decode(isyms.find(arc.ilabel))}
                sigma |= {pynini_utils.decode(osyms.find(arc.olabel))}
                print(sigma)
        return FsmSet(sigma)


    @property
    def sigma_star(self):
        """ Assemble infinite set of combinations of symbols.
        """

        return self.sigma.closure()

    def __len__(self):
        try:
            a = self.fst.paths()
        except pywrapfst.FstArgError:
            return float('inf')
        return len(list(a))

    def isEmpty(self):
        try:
            next(self.fst.paths())
        except StopIteration:
            return True
        except pywrapfst.FstArgError:
            return False
        return False

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

    # Operations that return a new FsmContainer
    ###########################################

    def closure(self):
        """ Return a FsmContainer containing the closure of items in this one.
        """
        cls = type(self)
        return cls.fromFst(fst=pynini.closure(self.fst),
                           keySerializer=self.keySerializer,
                           valueSerializer=self.valueSerializer)

    def project(self, side="key"):
        if side not in {"key", "value"}:
            raise ValueError

        project_output = (side == "value")

        if side == "key":
            codec = self.keySerializer
        else:
            codec = self.valueSerializer

        return FsmSet.fromFst(
                fst=self.fst.copy().project(project_output=project_output), 
                keySerializer=codec, 
                valueSerializer=codec)

    def copy(self):
        cls = type(self)
        out = cls.__new__(cls)
        for k, v in self.__dict__.items():
            setattr(out, k, v)
        return out

    # Iterator methods
    ##################


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
                raise ValueError(
                    "Unlimited iteration over cyclic (i.e. infinite)"
                    "FsmContainers is not supported. Specify a positive"
                    "integer as a value for limit.")
        else:
            stringpaths = pynini.shortestpath(self.fst, nshortest=limit).paths(
                input_token_type='symbol',
                output_token_type='symbol')
        if side=="key":
            for stringpath in stringpaths:
                yield self.keySerializer.inflate(
                        pynini_utils.decode(stringpath[0]))
        elif side=="value":
            for stringpath in stringpaths:
                yield self.keySerializer.inflate(
                        pynini_utils.decode(stringpath[1]))
        else:
            for stringpath in stringpaths:
                yield (self.keySerializer.inflate(
                            pynini_utils.decode(stringpath[0])),
                       self.keySerializer.inflate(
                            pynini_utils.decode(stringpath[1])))


@functools.total_ordering
class FsmSet(FsmContainer):

    # Constructors
    ##############

    def __init__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], FsmSet):
            return args[0].copy()
        as_set = set(*args, **kwargs)
        a = FsmSet.fromPairs((i, i) for i in as_set)
        self.fst = a.fst
        self.keySerializer = a.keySerializer
        self.valueSerializer = a.valueSerializer


    # Accessors and iterators
    #########################

    def unwrap(self):
        if self.isScalar():
            out, _, _ = next(self.fst.paths(input_token_type="symbol",
                                            output_token_type="symbol"))
            return self.keySerializer.unpack(out)
        else:
            raise ValueError("Cannot unwrap a set that contains more than"
                             "one item.")

    def draw(self, n=1):
        return pynini.randgen(self.fst, npath)

    def __iter__(self, limit=None):
        return self.paths(limit=limit, side="key")

    def __repr__(self):
        exampleItems = list(self.paths(limit=4, side="key"))
        exampleString = ", ".join("'%s'" % i for i in
                sorted(exampleItems)[0:3])
        if len(exampleItems) > 3:
            return "FsmSet({%s, ... })" % exampleString
        return "FsmSet({%s})" % exampleString

    # Binary ops
    ############

    __add__ = FsmContainer.binary_op(pynini.concat)
    __and__ = FsmContainer.binary_op(pynini.intersect)
    __or__  = FsmContainer.binary_op(pynini.union)
    __sub__ = FsmContainer.binary_op(pynini.difference)
    __xor__ = FsmContainer.binary_op(
                lambda self, other: (self | other) - (self & other))
    __mul__ = FsmContainer.product_op(pynini.compose)
    if six.PY3:
        __matmul__ = FsmContainer.product_op(pynini.leniently_compose)


    def __ge__(self, other):
        if not isinstance(other, FsmSet):
            raise TypeError
        if self.keySerializer != other.keySerializer:
            raise ValueError
        if (self - other) and not (other - self):
            return True
        return False

    # @functools.total_ordering takes care of other comparison operators after
    # we've specified these two.



class FsmMap(FsmContainer):

    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            if isinstance(args[0], dict):
                pairs = list(args[0].items())
            pairs = list(args[0])
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

    # Binary ops
    ############

    __add__ = FsmContainer.binary_op(pynini.concat)
    __or__  = FsmContainer.binary_op(pynini.union)
    __mul__ = FsmContainer.product_op(pynini.compose)
    if six.PY3:
        __matmul__ = FsmContainer.product_op(pynini.leniently_compose)


