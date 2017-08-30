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
from .wrappers import PyniniWrapper
import pywrapfst

class FsmContainer(object):
    """ A base class providing magic methods, and higher-order functions for
    creating magic methods, that are shared by FsmMap and FsmSet.
    """

    __projection_class__ = NotImplemented

    def __init__(self, *args, **kwargs):
        return NotImplemented

    @classmethod
    def fromPairs(cls, pairs, fsmWrapperClass=PyniniWrapper):
        self = cls.__new__(cls)

        keyPrototype, valuePrototype = pairs[0] if pairs else ("", "")
        self.keySerializer = Serializer.fromPrototype(keyPrototype)
        self.valueSerializer = Serializer.fromPrototype(valuePrototype)

        pairs = [(self.keySerializer.serialize(key), 
                  self.valueSerializer.serialize(value)) for key, value in pairs]
        self.fsm = fsmWrapperClass(pairs)

        return self

    def __len__(self):
        try:
            paths = self.fsm.pathIterator()
        except InfinitePathError:
            return float('inf')
        return len(list(paths))

    def __bool__(self):
        return not self.lenCompare(0, operator.eq)

    def __contains__(self, item):
        cls = type(self).__projection_class__
        item = cls({item})
        if item * self:
            return True
        return False

    def __eq__(self, other):
        return (self.keySerializer == other.keySerializer
                and self.valueSerializer == other.valueSerializer
                and self.fsm == other.fsm)

    def __add__(self, other):
        return self.doBinaryOp(other, op=self.fsm.concatenate)

    def __mul__(self, other):
        return self.doProductOp(other, op=self.fsm.compose)

    def __or__(self, other):
        return self.doBinaryOp(other, op=self.fsm.union)

    def doBinaryOp(self, other, op):
        if not type(other) == type(self):
            raise TypeError
        if self.keySerializer != other.keySerializer:
            raise ValueError
        if self.valueSerializer != other.valueSerializer:
            raise ValueError
        cls = type(self)
        obj = cls.__new__(cls)
        obj.fsm = op(self.fsm, other.fsm)
        obj.keySerializer = self.keySerializer
        obj.valueSerializer = self.valueSerializer
        return obj

    def doProductOp(self, other, op):
        if not isinstance(other, FsmContainer):
            raise TypeError
        if self.valueSerializer != other.keySerializer:
            raise ValueError
        cls = type(self)
        obj = cls.__new__(cls)
        obj.fsm = op(self.fsm, other.fsm)
        obj.keySerializer = self.keySerializer
        obj.valueSerializer = other.valueSerializer
        return obj

    def lenCompare(self, n, op=operator.eq):
            # __len__ can be expensive, but for the common case of
            # comparing  __len__ to a small integer
            # there is a cheap shortcut.
        numPathsToTryFor = n + 1
        try:
            p = self.fsm.pathIterator(limit=numPathsToTryFor)
            numPathsFound = len(list(p))
        except InfinitePathError:
            # Signals a cyclic FST with infinite length, which
            # can't equal any finite integer -- so False regardless of n.
            return False
        if op(numPathsFound, n):
            return True
        return False



@functools.total_ordering
class FsmSet(FsmContainer):

    def __init__(self, *args, **kwargs):
        """ Construct an FsmSet from any combination of arguments accepted
        by the builtin set() constructor. 
        """
        if len(args) == 1 and isinstance(args[0], FsmSet):
            return args[0].copy()
        as_set = set(*args, **kwargs)
        return FsmSet.fromPairs((i, i) for i in as_set)

    def __iter__(self, limit=None):
        return self.fsm.paths(limit=limit, side="key")

    def __repr__(self):
        exampleItems = list(self.fsm.paths(limit=4, side="key"))
        exampleString = ", ".join("'%s'" % i for i in
                sorted(exampleItems)[0:3])
        if len(exampleItems) > 3:
            return "FsmSet({%s, ... })" % exampleString
        return "FsmSet({%s})" % exampleString

    def __ge__(self, other):
        if not isinstance(other, FsmSet):
            raise TypeError
        if self.fsm.keySerializer != other.fsm.keySerializer:
            raise ValueError
        if (self - other) and not (other - self):
            return True
        return False


class FsmMap(FsmContainer):

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
        return type(self).fromPairs(pairs)

    @property
    def inv(self):
        return self.__invert__()

    def __invert__(self):
        return type(self).fromFsm(fsm=self.engine.invert(self.fsm),
                                  keySerializer=self.valueSerializer,
                                  valueSerializer=self.keySerializer,
                                  engine=self.engine)

    def __getitem__(self, key):
        cls = type(self).__projection_class__
        if isinstance(key, six.string_types):
            key = cls({key})
        elif not isinstance(key, cls):
            key = cls(key)

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
            return cls(form)

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



