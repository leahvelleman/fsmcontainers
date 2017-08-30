import unicodedata
import pytest
import six
from hypothesis import given, assume, reject
from hypothesis.strategies import *
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule
from fsmcontainers import *
from .tests import usabletext, transducertext


@composite
def fsmdicts(draw):
    pairs = draw(transducertext())
    return fsmdict(pairs)

@given(fsmdicts())
def test_keys_items_and_values_have_same_length(d):
    assert len(list(d.keys())) == len(list(d.values())) == len(list(d.items()))

@given(dictionaries(usabletext(), lists(usabletext(), min_size=1)))
def test_query_retrieves_all_of_the_input_mappings_values(d):
    pairs = [(k, v) for k in d for v in d[k]]
    a = fsmdict(pairs)
    for k in d:
        assert set(a.query(k)) == set(d[k])

@given(dictionaries(usabletext(), lists(usabletext(), min_size=1)))
def test_getitem_retrieves_one_of_the_input_mappings_values(d):
    pairs = [(k, v) for k in d for v in d[k]]
    a = fsmdict(pairs)
    for k in d:
        assert a[k] in d[k]

@given(dictionaries(usabletext(), usabletext()),
        one_of(dictionaries(usabletext(), usabletext()), nothing()))
def test_len_matches_set_length_of_input_mappings_items(d, kwargs):
    a = fsmdict(d, **kwargs)
    assert len(a) == len(set(d.items()) | set(kwargs.items()))

@given(lists(usabletext()), lists(usabletext()),
        one_of(dictionaries(usabletext(), usabletext()), nothing()))
def test_len_matches_set_length_of_input_iterable(l1, l2, kwargs):
    a = fsmdict(zip(l1, l2), **kwargs)
    assert len(a) == len(set(zip(l1, l2)) | set(kwargs.items()))

@given(usabletext(), one_of(dictionaries(usabletext(), usabletext()),
    nothing()))
def test_constructor_fails_with_sequence_with_wrong_size_elements(s, kwargs):
    assume(s)
    with pytest.raises(ValueError):
        a = fsmdict(s, **kwargs)
        assert a

@given(dictionaries(usabletext(), usabletext()),
        one_of(dictionaries(usabletext(), usabletext()), nothing()))
def test_mapping_constructor_with_dict_and_maybe_kwargs(d, kwargs):
    a = fsmdict(d, **kwargs)
    for k, v in d.items():
        assert v in a.query(k)
    for k, v in kwargs.items():
        assert v in a.query(k)

@given(lists(usabletext()), lists(usabletext()),
        one_of(dictionaries(usabletext(), usabletext()), nothing()))
def test_iterable_constructor_with_zip_and_maybe_kwargs(l1, l2, kwargs):
    a = fsmdict(zip(l1, l2), **kwargs)
    for k, v in zip(l1, l2):
        assert v in a.query(k)
    for k, v in kwargs.items():
        assert v in a.query(k)

@given(dictionaries(usabletext(), usabletext()))
def test_kwarg_constructor(kwargs):
    a = fsmdict(**kwargs)
    assert type(a) == fsmdict
    for k, v in kwargs.items():
        assert v in a.query(k)

def test_empty_constructor():
    a = fsmdict()
    assert type(a) == fsmdict




