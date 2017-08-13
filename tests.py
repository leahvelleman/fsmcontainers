import unicodedata
import pytest
import six
from hypothesis import given, assume
from hypothesis.strategies import *
from fstmapping import *

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
    a,b = obj
    assert FstCodec.from_prototype(a) == FstCodec.from_prototype(b)

@given(text())
def test_final_codec_retrieves_original_string(obj):
    c = FinalCodec
    assume(c.can_pack(obj))
    a = pynini.acceptor(obj, token_type="utf8")
    acceptorpath = next(a.paths(input_token_type="symbol"))[0]
    if isinstance(obj, six.text_type):
        assert c.decode(acceptorpath) == obj
    else:
        assert c.decode(acceptorpath).encode('utf8') == obj

@given(one_of(texttuples(), nonpackable()))
def test_final_codec_rejects_non_strings(obj):
    c = FinalCodec
    with pytest.raises(ValueError):
        c.encode(obj)

@given(data())
def test_final_codec_rejects_unbalanced_strings(d):
    a = d.draw(text().filter(braces_balanced))
    b = d.draw(text().filter(braces_balanced))
    obj = d.draw(sampled_from([
        a + "[" + b,
        a + "]" + b,
        "[[" + a + "]]" + b,
        "[" + a + "[" + b + "]]"]))
    c = FinalCodec
    with pytest.raises(ValueError):
        c.encode(obj)

@given(nonpackable())
def test_unsupported_prototype_error(obj):
    with pytest.raises(TypeError):
        FstCodec.from_prototype(obj)

@given(text())
def test_can_create_a_set_from_an_acceptor(obj):
    a = pynini.acceptor(obj, token_type="utf8")
    fs = FstSet(fst=a, kcodec=FstCodec.from_prototype(obj),
            vcodec=FstCodec.from_prototype(obj))
    assert isinstance(fs, FstSet)

@given(packable())
def test_can_create_a_set(obj):
    assume(all(not "\0" in o for o in obj))
    assert isinstance(FstSet(obj), FstSet)

@given(packable())
def test_can_lift_to_a_set(obj):
    c = FstCodec.from_prototype(obj)
    assume(c.can_pack(obj))
    assert isinstance(FstSet.lift(obj), FstSet)

@given(packable())
def test_lifted_objects_become_members(obj):
    c = FstCodec.from_prototype(obj)
    assume(c.can_pack(obj))
    a = FstSet.lift(obj)
    assert obj in a

@given(packable())
def test_lift_is_idempotent(obj):
    c = FstCodec.from_prototype(obj)
    assume(c.can_pack(obj))
    assert FstSet.lift(obj) == FstSet.lift(FstSet.lift(obj))

@given(packable())
def test_lower_is_inverse_of_lift(obj):
    assume(len(obj) > 0)
    c = FstCodec.from_prototype(obj)
    assume(c.can_pack(obj))
    a = FstSet.lift(obj)
    assert normalize_equal(a.lower(), obj)

@given(text())
def test_input_chars_appear_in_sigma_and_sigma_star(obj):
    c = FstCodec.from_prototype(obj)
    assume(c.can_pack(obj))
    a = FstSet.lift(obj)
    assert all(char in a.sigma() for char in obj)
    assert(obj in a.sigma_star())

@given(text())
def test_sets_are_truthy_iff_nonempty(obj):
    a = FstSet(obj)
    assert bool(a) == (len(obj)>0)

@given(packable(), packable())
def test_addition_lifts(obj1, obj2):
    a = FstSet.lift(obj1)
    b = FstSet.lift(obj2)
    try:
        assert a + obj2 == obj1 + b == a + b
        assert a + {obj2} == {obj1} + b == a + b
    except TypeError:
        pass

@given(packable(), packable())
def test_lowering_nonsingletons_does_nothing(obj1, obj2):
    assume(obj1 != obj2)
    assume(len(obj1)>0 and len(obj2)>0)
    a = FstSet(obj1)
    b = FstSet(obj2)
    assert (a|b).lower() == (a|b)


#@given(dss)
#def test_double_inversion_is_noop(d):
#    assume(len(d) > 0)
#    a = FstBidict(d)
#    assert a == ~~a
#
#@given(dss, dss, choices())
#def test_composition_is_application(d1, d2, cf):
#    assume(len(d1) > 0 and len(d2) > 0)
#    a = FstBidict(d1)
#    b = FstBidict(d2)
#    aob = a*b
#    assume([k for k in aob.keys()] != [])
#    k = cf([k for k in aob.keys()])
#    assert (a*b)[k] == b[a[k]]
#
#@given(dss, dss, choices())
#def test_concatenation_is_distributive(d1, d2, cf):
#    assume(len(d1) > 0 and len(d2) > 0)
#    a = FstBidict(d1)
#    b = FstBidict(d2)
#    apb = a+b
#    akey = cf([k for k in a.keys()])
#    bkey = cf([k for k in b.keys()])
#    assert apb[akey+bkey] == a[akey]+b[bkey]


def normalize_equal(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return unicodedata.normalize('NFC', a) == unicodedata.normalize('NFC',
                b)
    else:
        return a == b

