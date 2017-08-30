from itertools import chain
from collections import Mapping, Iterable
from .wrappers import PyniniWrapper
from .serializers import Serializer

class fsmcontainer(object):
    def __init__(self, *args, **kwargs):
        return NotImplemented

    def initializeWithPairs(self, pairs):
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

    def __contains__(self, key):
        return self.fsm.accepts(key)

    def __len__(self):
        return len(list(self.fsm.pathIterator()))

    def __iter__(self):
        return self.fsm.pathIterator(side="top")
        # Sides are equivalent for an fsmset; for an fsmdict, we want an
        # iterator over keys to match stdlib dict behavior, and keys are on
        # top.

    def __eq__(self, other):
        return self.fsm == other.fsm

class fsmdict(fsmcontainer):
    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError("fsmdict expected at most 1 arguments, got 2")
        arg = args[0] if args else []
        if isinstance(arg, Mapping):
            pairs = arg.items()
        else:
            pairs = arg.__iter__()
        pairs = chain(pairs, kwargs.items())
        self.initializeWithPairs(pairs)

    def __repr__(self):
        contents = repr(list(self.items()))
        return f"fsmdict({contents})"

    def __getitem__(self, key):
        return next(self.query(key))

    def query(self, key):
        keyFsm = PyniniWrapper.fromItem(self._serializeKey(key))
        for k, v in keyFsm.compose(self.fsm).pathIterator():
            yield self._inflateValue(v)    
                       # Eventually refactor this to return an fsmset, not an
                       # iterator

    def keys(self):
        return iter(self)

    def values(self):
        return self.fsm.pathIterator(side="bottom")

    def items(self):
        return self.fsm.pathIterator(side="both")
