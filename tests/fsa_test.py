import unicodedata
import pytest
import six
from itertools import tee
from hypothesis import given, assume, reject
from hypothesis.strategies import *
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule
from fsmcontainers import *
import random

usabletext = lambda: text(alphabet=characters(
    blacklist_characters=['\0', '\1'],
    blacklist_categories=['Cs']))

transducertext = lambda: lists(tuples(usabletext(), usabletext()))

def test_empty_constructor():
    a = fsa()
    assert type(a) == fsa

@given(iterables(usabletext()))
def test_nonempty_constructor(iterable):
    iterable, items = tee(iterable)
    a = fsa(iterable)
    for item in items:
        assert item in a

@given(lists(usabletext()), lists(usabletext()))
def test_boolean_ops_mirror_set_ops(xs, ys):
    x = fsa(xs)
    y = fsa(ys)
    for op in ['isdisjoint', 'issubset', 'issuperset', '__ge__', '__gt__',
               '__le__', '__lt__', '__eq__', '__ne__']:
        fOp = getattr(fsa, op)
        sOp = getattr(set, op)
        assert fOp(x, y) == sOp(set(xs), set(ys))

@given(lists(usabletext()), lists(usabletext()))
def test_constructive_ops_mirror_set_ops(xs, ys):
    x = fsa(xs)
    y = fsa(ys)
    for op in ['__or__', '__and__', '__xor__', '__sub__']:
        fOp = getattr(fsa, op)
        sOp = getattr(set, op)
        assert fOp(x, y) == fsa(sOp(set(xs), set(ys)))

@given(lists(usabletext()), lists(usabletext()), lists(usabletext()))
def test_constructive_operators_mirror_set_construction(xs, ys, zs):
    x = fsa(xs)
    y = fsa(ys)
    z = fsa(zs)
    for op in ['union', 'intersection', 'difference']:
        fOp = getattr(fsa, op)
        sOp = getattr(set, op)
        assert (fOp(x, y, z) == 
                fOp(x, y, set(zs)) == 
                fOp(x, set(ys), z) ==
                fOp(x, set(ys), set(zs)) ==
                fsa(sOp(set(xs), set(ys), set(zs))))

@given(lists(usabletext()), lists(usabletext()))
def test_concatenation(xs, ys):
    xset = fsa(xs)
    yset = fsa(ys)
    zset = xset + yset
    for x in xs:
        for y in ys:
            assert x + y in zset


