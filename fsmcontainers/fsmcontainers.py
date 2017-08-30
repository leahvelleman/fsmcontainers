from itertools import chain
from collections import Mapping, Iterable
from .wrappers import PyniniWrapper
from .serializers import Serializer

class fsmcontainer(object):
    def __init__(self, *args, **kwargs):
        return NotImplemented

    def initializeWithPairs(self, pairs):
        self.fsm = PyniniWrapper.fromPairs(pairs)

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
        keyFsm = PyniniWrapper.fromItem(key)
        for k, v in keyFsm.compose(self.fsm).pathIterator():
            yield v    # Eventually refactor this to return an fsmset, not an
                       # iterator

    def keys(self):
        return iter(self)

    def values(self):
        return self.fsm.pathIterator(side="bottom")

    def items(self):
        return self.fsm.pathIterator(side="both")
