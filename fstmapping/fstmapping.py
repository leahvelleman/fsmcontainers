# pylint: disable=fixme
import collections
import pynini
import pywrapfst
import six
from .pynini_utils import apply_down, apply_up, get_sigma,\
        upper_words, lower_words, m


class FstMapping(collections.Mapping):

    encodemapper = pynini.EncodeMapper("standard", True, True)

    def __init__(self, *args, **kwargs):
        parent = kwargs['parent'] or None
        max_iter = kwargs['max_iter'] or 10000
        self.max_iter = max_iter
        if parent is not None:
            self.fst = pynini.invert(parent.fst)
            self.inv = parent
        else:
            self.fst = self._setup_fst(args)
            self.inv = FstMapping(parent=self)

    def _setup_fst(self, args):
        if len(args) == 1:
            if isinstance(args[0], pynini.Fst):
                return args[0]
            if isinstance(args[0], FstMapping):
                return args[0].fst
            if isinstance(args[0], collections.Iterable):
                return m(args[0])
        if all(isinstance(arg, six.string_types) for arg in args):
            return m((arg, arg) for arg in args)
        if all(isinstance(arg, tuple) for arg in args):
            return m(*args)
        raise ValueError

    # TODO: memoize
    def sigma(self):
        return m(get_sigma(self.fst.output_symbols()))

    # TODO: memoize, make sure we're giving out COPIES of the iterator so
    # we don't give out a half-eaten one by mistake
    def keys(self):
        return upper_words(self.fst, limit=self.max_iter)

    def __eq__(self, other):
        return self.fst == other.fst

    def __len__(self):
        return self.max_iter or len([k for k in self.keys()])

    def __hash__(self):
        return hash(self.fst.write_to_string())

    def __invert__(self):
        return self.inv

    def __and__(self, other):
        return FstMapping(pynini.intersect(self.fst, other.fst))

    def __or__(self, other):
        return FstMapping(pynini.union(self.fst, other.fst))

    def __mul__(self, other):
        return FstMapping(pynini.compose(self.fst, other.fst))

    def __add__(self, other):
        return FstMapping(pynini.concat(self.fst, other.fst))

    def __getstate__(self):
        state = self.__dict__.copy()
        state['fst'] = state['fst'].write_to_string()
        state['sigma'] = state['sigma'].write_to_string()
        return state

    def __setstate__(self, state):
        #pylint: disable=no-member
        #(pywrapfst doesn't properly advertise that its Fst member exists.)
        self.__dict__.update(state)
        self.fst = pynini.Fst.from_pywrapfst(
            pywrapfst.Fst.read_from_string(state['fst']))
        self.sigma = pynini.Fst.from_pywrapfst(
            pywrapfst.Fst.read_from_string(state['sigma']))

    def __getitem__(self, key):
        if isinstance(key, set):
            form = set.union(*(apply_down(self.fst, item) for item in key))
        elif isinstance(key, six.string_types):
            form = apply_down(self.fst, key)
        else:
            raise TypeError
        if not form:
            raise KeyError
        return form

    def __iter__(self):
        for word in self.keys():
            yield word, self[word]

    def __contains__(self, key):
        try:
            if self[key]:
                return True
        except KeyError:
            return False
