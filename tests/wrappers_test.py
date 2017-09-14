"""
Automatically construct class members? Or find a way to make sure my stateful
tests are tracking the class as it gets changed, including all operations etc?

To test:
    - Object-returning methods give an object of the right type.
        (__getitem__, keys, values, items, paths)
    - Containers that hash equal have the same properties.
    - Set total ordering is transitive, antireflexive, WHAT ELSE?
    - m[{a,b}] == m[a] | m[b]
    - m[∅] is KeyError
    - {item for item in FsmSet(*args, **kwargs)} == set(*args, **kwargs)
    - {k:v for k,v in FsmDict(*args, **kwargs).items()} == dict(*args, **kwargs)
    - With the exception of subscripting with a set, if S is an FsmSet and s is
      a regular set then S.method(*args, **kwargs) == s.method(*args, **kwargs)
    - Same for D and d
    - a * (b+c) == (a*b) + (a*c)
    - a & (b|c) == (a&b) | (a&c)
"""

import unicodedata
import pytest
import six
from hypothesis import given, assume, reject
from hypothesis.strategies import *
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule
from fsmcontainers import *
from fsmcontainers.fsmcontainers.serializers import Serializer, braces_balanced
from fsmcontainers.fsmcontainers.wrappers import PyniniWrapper
from random import shuffle

@composite
def texttuples(draw, n=None):
    if not n:
        n = draw(integers(min_value=1, max_value=9))
    return tuple(draw(text()) for i in range(n))

@composite
def matchingtexttuples(draw):
    n = draw(integers(min_value=1, max_value=9))
    return tuple(draw(text()) for i in range(n)), tuple(draw(text()) for i in
            range(n))

def textpairs():
    return texttuples(2)

def texttriples():
    return texttuples(3)

@composite
def packable(draw):
    return draw(one_of(text(), texttuples()))

@composite
def nonpackable(draw):
    return draw(one_of(dictionaries(text(), text()), integers()))


Text = text()
TextPairs = tuples(Text, Text)
TextTriples = tuples(Text, Text, Text)
TextTuples = one_of(TextPairs, TextTriples)

    

@given(matchingtexttuples())
def test_codec_from_prototype_is_function_of_type_alone(obj):
    a, b = obj
    assert Serializer.from_prototype(a) == Serializer.from_prototype(b)

@given(one_of(text(), texttuples()))
def test_can_serialize_and_inflate(obj):
    s = Serializer.from_prototype(obj)
    try:
        assert s.inflate(s.serialize(obj)) == obj
    except ValueError:
        reject()

@given(data())
def test_cannot_serialize_unbalanced_strings(d):
    a = d.draw(text().filter(braces_balanced))
    b = d.draw(text().filter(braces_balanced))
    obj = d.draw(sampled_from([
        a + "[" + b,
        a + "]" + b,
        "[[" + a + "]]" + b,
        "[" + a + "[" + b + "]]"]))
    s = Serializer.from_prototype(obj)
    with pytest.raises(ValueError):
        s.serialize(obj)

@given(nonpackable())
def test_unsupported_prototype_error(obj):
    with pytest.raises(TypeError):
        Serializer.from_prototype(obj)

usabletext = lambda: text(alphabet=characters(
    blacklist_characters=['\0', '\1'],
    blacklist_categories=['Cs']))

transducertext = lambda: lists(tuples(usabletext(), usabletext()))

@composite
def acceptortext(draw):
    n = draw(lists(usabletext()))
    return list(zip(n,n))

@composite
def transducers(draw):
    pairs = draw(transducertext())
    transducer = PyniniWrapper.fromPairs(pairs)
    return transducer

@given(transducertext())
def test_wrapper_from_pairs(items):
    assume(items)
    wrapper = PyniniWrapper.fromPairs(items)
    assert wrapper

@given(transducertext())
def test_item_order_is_unimportant(items):
    assume(items)
    wrapper1 = PyniniWrapper.fromPairs(items)
    shuffle(items)
    wrapper2 = PyniniWrapper.fromPairs(items)
    assert wrapper1 == wrapper2

@given(transducertext())
def test_input_items_are_accepted(items):
    assume(items)
    wrapper = PyniniWrapper.fromPairs(items)
    for item in items:
        assert wrapper.accepts(item[0], side="top")
        assert wrapper.accepts(item[1], side="bottom")

@given(transducertext(), transducertext())
def test_noninput_items_are_not_accepted(items, redHerrings):
    assume(items)
    tops, bottoms = zip(*items)
    wrapper = PyniniWrapper.fromPairs(items)
    for rh in redHerrings:
        if rh[0] in tops and rh[1] in bottoms:
            reject()
        if rh[0] not in tops:
            assert not wrapper.accepts(rh[0], side="top")
        if rh[1] not in bottoms:
            assert not wrapper.accepts(rh[1], side="bottom")

@given(transducertext())
def test_pathIterator_sidedness(items):
    keys = [item[0] for item in items]
    values = [item[1] for item in items]
    wrapper = PyniniWrapper.fromPairs(items)
    assert set(keys) == set(wrapper.pathIterator(side="top"))
    assert set(values) == set(wrapper.pathIterator(side="bottom"))
    assert set(items) == set(wrapper.pathIterator(side=None))

@given(transducertext(), transducertext())
def test_concatenation(items1, items2):
    assume(items1)
    assume(items2)
    wrapper1 = PyniniWrapper.fromPairs(items1)
    wrapper2 = PyniniWrapper.fromPairs(items2)
    result = wrapper1.concatenate(wrapper2)
    paths = result.pathIterator(side=None)
    manualResult = []
    for i1 in items1:
        for i2 in items2:
            manualResult += [(i1[0]+i2[0], i1[1]+i2[1])]
    assert set(manualResult) == set(paths)

@given(transducertext(), transducertext())
def test_transducer_union_mimics_set_union(items1, items2):
    assume(items1)
    assume(items2)
    wrapper1 = PyniniWrapper.fromPairs(items1)
    wrapper2 = PyniniWrapper.fromPairs(items2)
    result = set(wrapper1.union(wrapper2).pathIterator(side=None))
    manualResult = set(items1) | set(items2)
    assert result == manualResult

@given(acceptortext(), acceptortext())
def test_acceptor_intersection_mimics_set_intersection(items1, items2):
    assume(items1)
    assume(items2)
    wrapper1 = PyniniWrapper.fromPairs(items1)
    wrapper2 = PyniniWrapper.fromPairs(items2)
    result = set(wrapper1.intersect(wrapper2).pathIterator(side=None))
    manualResult = set(items1) & set(items2)
    assert result == manualResult

@given(acceptortext(), acceptortext())
def test_acceptor_subtraction_mimics_set_subtraction(items1, items2):
    assume(items1)
    assume(items2)
    wrapper1 = PyniniWrapper.fromPairs(items1)
    wrapper2 = PyniniWrapper.fromPairs(items2)
    result = set(wrapper1.subtract(wrapper2).pathIterator(side=None))
    manualResult = set(items1) - set(items2)
    assert result == manualResult

@given(transducertext())
def test_projection(items):
    assume(items)
    tops, bottoms = zip(*items)
    wrapper = PyniniWrapper.fromPairs(items)
    topwrapper = wrapper.project(side="top")
    bottomwrapper = wrapper.project(side="bottom")
    for i in tops:
        assert topwrapper.accepts(i)
        if i not in bottoms:
            assert not bottomwrapper.accepts(i)
    for i in bottoms:
        assert bottomwrapper.accepts(i)
        if i not in bottoms:
            assert not bottomwrapper.accepts(i)

@given(transducertext(), integers(min_value=0, max_value=5))
def test_star(items, n):
    assume(items)
    wrapper = PyniniWrapper.fromPairs(items).star()
    for i in items:
        assert wrapper.accepts(i[0]*n, side="top")
        assert wrapper.accepts(i[1]*n, side="bottom")


def normalize_equal(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return unicodedata.normalize('NFC', a) == unicodedata.normalize('NFC',
                b)
    else:
        return a == b

