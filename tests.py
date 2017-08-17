import unicodedata
import pytest
import six
from hypothesis import given, assume, reject
from hypothesis.strategies import *
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule
from fsmcontainers import *

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

@given(text())
def test_can_create_a_set_from_an_acceptor(obj):
    a = pynini.acceptor(obj, token_type="utf8")
    fs = FsmSet.fromFst(fst=a,
                        keySerializer=Serializer.from_prototype(obj),
                        valueSerializer=Serializer.from_prototype(obj))
    assert isinstance(fs, FsmSet)

@given(packable())
def test_can_create_a_set(obj):
    assume(all(not "\0" in o for o in obj))
    try:
        fs = FsmSet(obj)
    except ValueError:
        reject()
    assert isinstance(fs, FsmSet)

@given(text())
def test_input_chars_appear_in_sigma(obj):
    assume(obj != '')
    try:
        assert FsmSet(obj) == FsmSet({obj}).sigma
    except ValueError:
        reject()

@given(text())
def test_sets_are_truthy_iff_nonempty(obj):
    try:
        a = FsmSet(obj)
    except ValueError:
        reject()
    assert bool(a) == (len(obj) > 0)

# TODO:
#   FstSet({1:2}) == FstSet({1})?
#   Are there other set constructor possibilities we're overlooking?


@given(dictionaries(text(), text()))
def test_double_inversion_is_noop(d):
    assume(len(d) > 0)
    try:
        a = FsmMap(d)
    except ValueError:
        reject()
    assert a == ~~a

@given(dictionaries(text(), text()), dictionaries(text(), text()), choices())
def test_composition_is_application(d1, d2, cf):
    assume(len(d1) > 0 and len(d2) > 0)
    try:
        a = FsmMap(d1)
        b = FsmMap(d2)
    except ValueError:
        reject()
    aob = a*b
    assume([k for k in aob.keys()] != [])
    k = cf([k for k in aob.keys()])
    assert (a*b)[k] == b[a[k]]

@given(dictionaries(text(), text()), dictionaries(text(), text()), choices())
def test_concatenation_is_distributive(d1, d2, cf):
    assume(len(d1) > 0 and len(d2) > 0)
    try:
        a = FsmMap(d1)
        b = FsmMap(d2)
    except ValueError:
        reject()
    apb = a+b
    akey = cf([k for k in a.keys()])
    bkey = cf([k for k in b.keys()])
    assert apb[akey+bkey] == a[akey]+b[bkey]

class FsmSets(RuleBasedStateMachine):
    fsmsets = Bundle('FsmSet')

    @rule(target=fsmsets, x=text())
    def acceptor(self, x):
        try:
            return FsmSet({x})
        except ValueError:
            reject()

    @rule(target=fsmsets, x=fsmsets, y=fsmsets)
    def union(self, x, y):
        return x|y

    @rule(target=fsmsets, x=fsmsets, y=fsmsets)
    def intersection(self, x, y):
        return x&y

    @rule(target=fsmsets, x=fsmsets, y=fsmsets)
    def concatenation(self, x, y):
        return x+y

    @rule(target=fsmsets, x=fsmsets, y=fsmsets)
    def subtraction(self, x, y):
        return x-y

    @rule(target=fsmsets, x=fsmsets)
    def closure(self, x):
        return x.closure()

    @rule(x=fsmsets, y=fsmsets)
    def test_intersections_are_subsets(self, x, y):
        assert x&y <= x


TestSets = FsmSets.TestCase

def normalize_equal(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return unicodedata.normalize('NFC', a) == unicodedata.normalize('NFC',
                b)
    else:
        return a == b

