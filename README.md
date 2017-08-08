# fstmapping

A Pythonic interface for finite state transducers.

An FstMapping is a Python mapping -- a dictionary-like object -- backed by a finite state transducer. 

```python
>>> m = FstMapping({"a": "b"})
>>> m["a"]
"b"
```

## Reversible, composable, concatenable, intersectable...

Unlike regular dictionaries, they are reversible. The reverse can be accessed using the .inv property or the ~ operator.

```python
>>> m.inv["b"]
"a"
>>> (~m)["b"]
"a"
>>> (~m)["a"]
KeyError
>>> ~~m == m
True
```

Other common FST operators are supported as well: * for composition, + for concatenation, | for union, and & for intersection.

```python
>>> n = FstMapping({"b": "c"})
>>> (m*n)["a"]
"c"
>>> (m+n)["ab"]
"bc"
>>> (m|n)["a"]
"b"
>>> (m|n)["b"]
"c"
```

## One-to-many

Unlike regular dictionaries, FstMappings can be one-to-many. When a key is mapped to many values, the values are returned as a set.

```python
>>> m2 = FstMapping({"a": "c", "b": "c"})
>>> (~m2)["c"] == {"a", "b"}
True
```

Sets can also be used as keys. `m[{a,b,...,z}]` is syntactic sugar for `set(m[a])+set(m[b])+...+set(m[z])`. This gives the 
convenient properties that any value in `m` can serve as a key for `~m` and that `~m*m` maps every value in `m.values()` to itself. 
It also preserves the identity `(m*n)[a]==n[m[a]]`.

```python
>>> m2[{"a", "b"}]
"c"
>>> (~m2*m2)["c"]
"c"
```

## Potentially infinite

FstMappings can be based on a cyclic FST. This means that, unlike dictionaries, they can support mappings that take
a (theoretically) infinite number of keys, or return a (theoretically) infinite number of different values, or both. 
For instance, this transducer maps a string of `a`s of any length to a string of `b`s of equal length.

```python
>>> import pynini
>>> m3 = FstMapping(pynini.transducer("a", "b").closure())
>>> m3["aaaaa"]
"bbbbb"
>>> m3["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
```

If `m` is cyclic on its key side, `len(m)`, `m.keys()`, `m.values()` and `m.items()` raise errors. If `m` is cyclic on its value
side and maps `k` to an infinite number of values, then `m[k]` and `m.get(k)` also raise errors.

