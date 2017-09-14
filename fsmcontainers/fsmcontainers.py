from itertools import chain
from collections import Mapping, Iterable
from numbers import Number
import operator
from .wrappers import PyniniWrapper
from .serializers import Serializer

SIGMA = list("qwertyuiopasdfghjkl;'zxcvbnm,./`1234567890-=QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?~!@#$%^&*()_+ ")

class fsmcontainer(object):
    def __init__(self, *args, **kwargs):
        return NotImplemented

    def _initializeWithPairs(self, pairs):
        try:
            kproto, vproto, rest = *next(pairs), pairs
                # Try popping off a (k,v) pair to serve as prototypes for
                # serializers.
            pairs = chain([(kproto, vproto)], rest)
                # Reinsert the pair we popped at the head of the chain.
                # This saves eagerly constructing a complete list just so we
                # can index its first item.
        except StopIteration:
            kproto, vproto = ("", "")
        self.keySerializer = Serializer.from_prototype(kproto)
        self.valueSerializer = Serializer.from_prototype(vproto)
        self.fsm = PyniniWrapper.fromPairs(self._serializePair(p)
                                            for p in pairs)

    def _initializeWithAttributes(self, fsm,
            keySerializer=Serializer.from_prototype(""),
            valueSerializer=Serializer.from_prototype("")):
        self.keySerializer = keySerializer
        self.valueSerializer = valueSerializer
        self.fsm = fsm

    def _initializeAsCopy(self, other):
        self.keySerializer = other.keySerializer
        self.valueSerializer = other.valueSerializer
        self.fsm = other.fsm

    @classmethod
    def fromAttributes(cls, fsm, keySerializer, valueSerializer):
        obj = cls.__new__(cls)
        obj._initializeWithAttributes(fsm, keySerializer, valueSerializer)
        return obj

    def _serializePair(self, pair):
        k, v = pair
        return (self._serializeKey(k), self._serializeValue(v))

    def _serializeKey(self, key):
        return self.keySerializer.serialize(key)

    def _serializeValue(self, value):
        return self.valueSerializer.serialize(value)

    def _inflatePair(self, pair):
        k, v = pair
        return (self._inflateKey(k), self._inflateValue(v))

    def _inflateKey(self, key):
        return self.keySerializer.inflate(key)

    def _inflateValue(self, value):
        return self.valueSerializer.inflate(value)

    def __add__(self, other):
        return self._binaryOp(other, op=self.fsm.concatenate)

    def concatenate(self, *others):
        """
        Return an :class:`fsa` whose elements are made up of an element
        of *s* concatenated with an element of *t*.

        >>> this = fsa('a', 'b')
        >>> other = fsa('c', 'd')
        >>> sorted(this + other)
        ['ac', 'ad', 'bc', 'bd']
        """
        obj = self.copy()
        cls = type(self)
        for other in others:
            obj = obj + cls(other)
        return obj

    def __or__(self, other):
        return self._binaryOp(other, op=self.fsm.union)

    def union(self, *others):
        obj = self.copy()
        cls = type(self)
        for other in others:
            obj = obj | cls(other)
        return obj

    def _binaryOp(self, other, op):
        cls = type(self)
        self._typecheck(other)
        return cls.fromAttributes(
                fsm=op(other.fsm),
                keySerializer=self.keySerializer,
                valueSerializer=other.valueSerializer)

    def _productOp(self, other, operator, cls=None):
        cls = cls or type(self)
        if self.valueSerializer != other.keySerializer:
            raise ValueError
        return cls.fromAttributes(fsm=operator(other.fsm),
                                  keySerializer=self.keySerializer,
                                  valueSerializer=other.valueSerializer)

    def _typecheck(self, *others):
        for other in others:
            if self.keySerializer != other.keySerializer:
                raise ValueError
            if self.valueSerializer != other.valueSerializer:
                raise ValueError

    def __contains__(self, key):
        return self.fsm.accepts(key)

    def __len__(self):
        """
        Return the number of elements in *a*. If *a* is a cyclic acceptor with an
        infinite number of elements, return :literal:`float('inf')`.
        """
        return len(list(self.fsm.pathIterator()))

    def len_compare(self, n, op=operator.eq):
        """
        With a number as the positional argument, return True if the number of
        elements in this instance is equal to *n* and False otherwise. Or, if a
        different comparison operator is specified, return the result of applying
        that operator to the number of elements and *n*.

         >>> a = fsa({'one', 'two', 'three'})
         >>> a.len_compare(3)
         True
         >>> a.len_compare(4, operator.ge)
         False
         >>> a.len_compare(4, operator.lt)
         True

        With an iterable as the positional argument, return True if the number of
        elements in this instance is the same as the number of elements in
        *other*, which may be an :class:`fsa` or any other iterable. Or, if a
        different comparison operator is specified, return the result of applying
        that operator to the number of elements in this instance and in *other*.

         >>> a = fsa({'one', 'two', 'three'})
         >>> a.len_compare(['four', 'five', 'six'])
         True
         >>> a.len_compare("dog")
         True
         >>> a.len_compare("aardvark")
         False
    """
        if n == float('inf'):
            return self.fsm.isCyclic()
        if isinstance(n, Iterable):
            return self.fsm.numPathsCompare(len(n), op)
        return self.fsm.numPathsCompare(n, op)

    def __iter__(self):
        return self._items("top")
        # Sides are equivalent for an fsmset; for an fst, we want an
        # iterator over keys to match stdlib dict behavior, and keys are on
        # top.

    def _items(self, side, limit=None):
        if side == "both":
            return ((self._inflateKey(k), self._inflateValue(v))
                    for k, v in self.fsm.pathIterator(side="both", limit=limit))
        elif side == "top":
            return (self._inflateKey(k) for k in
                    self.fsm.pathIterator(side="top", limit=limit))
        elif side == "bottom":
            return (self._inflateValue(v) for v in
                    self.fsm.pathIterator(side="bottom", limit=limit))

    def __eq__(self, other):
        cls = type(self)
        other = cls(other)
        return self.fsm == other.fsm

    def copy(self):
        cls = type(self)
        return cls.fromAttributes(self.fsm,
                                  self.keySerializer,
                                  self.valueSerializer)
        return obj

    def _repr(self, side):
        contents = list(self._items(side=side, limit=5))
        coda = " ... " if len(contents) > 4 else ""
        contents = ", ".join(map(repr, contents[:4])) + coda
        cls = type(self).__name__
        return f"{cls}([{contents}])"

    def star(self):
        """
        Return an :class:`fsa` whose elements are made by concatenating
        together zero or more elements from the current instance.

             >>> s = fsa({'a', 'b'}).star()
             >>> 'a' in s
             True
             >>> 'babbbbaabaaaaa' in s
             True
             >>> '' in s
             True
             >>> 'c' in s
             False
        """
        cls = type(self)
        return cls.fromAttributes(self.fsm.star(), self.keySerializer,
                self.valueSerializer)

    def plus(self):
        """
        Return an :class:`fsa` whose elements are made by concatenating
        together one or more elements from the current instance.
      
             >>> t = fsa({'a', 'b'}).plus()
             >>> 'a' in t
             True
             >>> 'aababbbababbba' in t
             True
             >>> '' in t
             False
             >>> 'c' in t
             False
        """
        cls = type(self)
        return cls.fromAttributes(self.fsm.plus(), self.keySerializer,
                self.valueSerializer)


class fsa(fsmcontainer):
    """
    Return a new finite state acceptor. The acceptor behaves like a set whose
    elements are *items*, or are taken from *iterator.* Elements must all be
    strings, or must all be members of another class that implements
    :literal:`fsm_serialize` and :literal:`fsm_deserialize` methods for
    conversion to and from strings.

    If no arguments are specified, the result is an :class:`fsa` that
    behaves like an empty set. 

      >>> a = fsa()
      >>> len(a)
      0

    If one or more arguments are specified, and all are valid elements, they
    become elements of the :class:`fsa`.

      >>> a = fsa('a single long string argument') 
      >>> a
      fsa(['a single long string argument'])
      >>> len(a)
      1
      >>> a = fsa('one', 'two', 'three')
      >>> len(a)
      3

    If a single iterable is specified, and its items are valid elements, they
    become elements of the :class:`fsa`.

      >>> a = fsa(['a', 'sequence', 'of', 'short', 'strings'])
      >>> len(a)
      5
      >>> a == set(['a', 'sequence', 'of', 'short', 'strings'])
      True
    """

    def __init__(self, *items):
        # single argument is an fsa -- copy it and quit
        if len(items) == 1 and isinstance(items[0], type(self)):
            self._initializeAsCopy(items[0])
            return

        # single argument is a list -- unpack it and continue
        elif (len(items) == 1 and isinstance(items[0], Iterable) and not 
                isinstance(items[0], str)):
            items = items[0]

        # multiple str arguments, or a single iterable[str] that got unpacked,
        # or a single empty iterable that got unpacked, or no arguments at all
        if all(isinstance(i, str) for i in items):
            pairs = ((i, i) for i in items)
            self._initializeWithPairs(pairs)

        # some other combination of arguments
        else:
            raise TypeError


    def __repr__(self):
        return self._repr(side="top")

    def isdisjoint(self, other):
        return not self.fsm.intersect(other.fsm).hasPaths()

    def issubset(self, other):
        return not self.fsm.subtract(other.fsm).hasPaths()

    def issuperset(self, other):
        return not other.fsm.subtract(self.fsm).hasPaths()

    def __le__(self, other):
        return self.issubset(other)

    def __lt__(self, other):
        return self.issubset(other) and not self == other

    def __ge__(self, other):
        return self.issuperset(other)

    def __gt__(self, other):
        return self.issuperset(other) and not self == other

    def __sub__(self, other):
        return self._binaryOp(other, op=self.fsm.subtract)

    def difference(self, *others):
        obj = self.copy()
        cls = type(self)
        for other in others:
            obj = obj - cls(other)
        return obj

    def __and__(self, other):
        return self._binaryOp(other, op=self.fsm.intersect)

    def intersection(self, *others):
        obj = self.copy()
        cls = type(self)
        for other in others:
            obj = obj & cls(other)
        return obj

    def __xor__(self, other):
        return (self - other) | (other - self)

    def __mul__(self, other):
        return self._productOp(other, self.fsm.cross, cls=fst)

    def cross(self, other):
        """
        Return an :class:`fst` representing the cross product of *this*
        and *other.* The resulting fst maps each value in *this* to each value
        in *other*.

        >>> this = fsa('a', 'b')
        >>> other = fsa('1', '2')
        >>> sorted((this * other).items())
        [('a', '1'), ('a', '2'), ('b', '1'), ('b', '2')]
        """
        return self * other

    def __invert__(self):
        """
        Return an :class:`fst` containing all strings not in this one.

        >>> 'a' in ~fsa('a')
        False
        >>> 'b' in ~fsa('a')
        True
        >>> 'asdfkhasdfkasdfhkjlasdhkasdjfas' in ~fsa('a')
        True
        """
        cls = type(self)
        return cls(SIGMA).star() - self

    def becomes(self, other):
        this = self.fsm
        thisKS = self.keySerializer
        if isinstance(other, fsmcontainer):
            that = other.fsm 
            thatVS = other.valueSerializer
        else:
            that = PyniniWrapper.fromItem(other)
            thatVS = Serializer.from_prototype(other)
        return fst.fromAttributes(
                fsm=PyniniWrapper.transducer(this, that),
                keySerializer=thisKS,
                valueSerializer=thatVS)


class fst(fsmcontainer):
    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError("fst expected at most 1 arguments, got 2")
        arg = args[0] if args else []
        if isinstance(arg, type(self)):
            self._initializeAsCopy(arg)
        else:
            if isinstance(arg, Mapping):
                pairs = arg.items()
            else:
                pairs = arg.__iter__()
            pairs = chain(pairs, kwargs.items())
            self._initializeWithPairs(pairs)

    def __repr__(self):
        return self._repr(side="both")

    def __getitem__(self, key):
        return next(iter(self.query({key})))

    def __matmul__(self, other):
        return self._productOp(other, self.fsm.compose, cls=type(self))

    def __rmatmul__(self, other):
        return other._productOp(self, other.fsm.compose, cls=type(self))

    def __truediv__(self, other):
        return self | (~self.keyset() @ other)

    def priority_union(self, *others):
        obj = self.copy()
        cls = type(self)
        for other in others:
            obj = obj / cls(other)
        return obj

    def query(self, querySet):
        return (fsa(querySet) @ self).valueset()

    def keys(self):
        return self._items(side="top")

    def keyset(self):
        return fsa.fromAttributes(fsm=self.fsm.project(side="top"), 
                                     keySerializer=self.valueSerializer,
                                     valueSerializer=self.valueSerializer)

    def values(self):
        return self._items(side="bottom")

    def valueset(self):
        return fsa.fromAttributes(fsm=self.fsm.project(side="bottom"), 
                                     keySerializer=self.valueSerializer,
                                     valueSerializer=self.valueSerializer)

    def items(self):
        return self._items(side="both")

    def between(self, left="", right=""):
        left = fsa(left)
        right = fsa(right)
        sigma = fsa(SIGMA).star()
        self._typecheck(left, right)
        return fst.fromAttributes(
                fsm = self.fsm.makeRewrite(left.fsm, right.fsm, sigma=sigma.fsm),
                keySerializer = self.keySerializer,
                valueSerializer = self.valueSerializer)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
