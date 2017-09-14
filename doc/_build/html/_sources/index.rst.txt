.. fsmcontainers documentation master file, created by
   sphinx-quickstart on Tue Sep  5 18:13:01 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

fsmcontainers
=============

.. module:: fsmcontainers.fsmcontainers

.. testsetup:: *

   from fsmcontainers.fsmcontainers import fsa, fst
   import operator

This module provides two classes:

   * :class:`fsa`, a finite-state acceptor that behaves like a Python set.
   * :class:`fst`, a finite-state transducer that behaves like a Python dict.

These offer a Pythonic interface for using finite-state linguistic
resources or hand-coding new ones.

    >>> with open('piglatin.fst') as f:
    ...    piglatin = fsa.load(f)

    >>> sentence = 'do you speak pig latin'
    >>> ''.join([piglatin[w] for w in sentence.split()])
    'oday ouyay eakspay igpay atinlay'

    >>> sentence = 'Pig Latin, or "{pig latin}," is spoken by...'
    >>> sentence.format_map(piglatin)
    'Pig Latin, or "igpay atinlay," is spoken by...'

They are **not** meant to be high-performance replacements for
built-in :class:`set` and :class:`dict`.  For very large finite sets of strings
or mappings between strings, use askdhfa.  For high-performance
potentially-infinite sets of strings, you may be able to use regular
expressions, with :func:`re.match` as a test of set membership.

Both classes provide additional operations that are useful in computational
morphology, including cross product (:literal:`*`), composition (:literal:`@`),
and methods for constructing context-dependent rewrite rules (:meth:`fst.before`,
:meth:`fst.after`, :meth:`fst.between`, and :meth:`fst.anywhere`).

Contents
--------

    * `Finite state acceptors`_
    * `Finite state transducers`_
    * `Shared operations`_ which apply to both acceptors and transducers
    * `Linguistic applications`_


Finite state acceptors
----------------------

.. class:: fsa(iterable)
.. autoclass:: fsa

   Unlike sets, acceptors can have an infinite number of elements. But
   iterables passed to :class:`fsa` are eagerly evaluated, and so must be
   finite.  If, for instance, :class:`fsa` is passed a generator that never
   raises :literal:`StopIteration`, it will draw new values endlessly and never
   return.  To create a new infinite acceptor, use :meth:`plus` or :meth:`star`
   on a finite acceptor, or use other operations on an existing infinite
   acceptor. [#f1]_

   Instances of :class:`fsa` provide all the same operations as built-in
   Python :class:`set`, and compare equal to built-in sets with the same
   elements::

     >>> fsa('one', 'two', 'three') & {'three', 'four', 'five'}
     fsa('three')
     >>> fsa('one', 'two') == {'one', 'two'}
     True
     >>> fsa('one', 'two') > {'one'}
     True

   In addition, instances of :class:`fsa` provide all of the `shared
   operations`_, as well as the following operation:

   .. describe:: this * other
   .. automethod:: cross




Finite state transducers
------------------------

.. class:: fst(**kwargs)
           fst(mapping, **kwargs)
           fst(iterable, **kwargs) 

   |a** Return| a new finite state transducer. The transducer behaves like a
   dictionary or other mapping object, and :class:`fst` can be called with any
   of the same argument combinations as :class:`dict`, with the same semantics
   --- subject only to the restriction that its keys and values must be strings,
   or must be serializable to strings.

   >>> a = fst([('a', 'b'), ('c', 'd')], e='f', g='h')
   >>> a['a']
   'b'
   >>> a['e']
   'f'

   In addition, fsts can map a single key to more than one value.  To create an
   :class:`fst` with this property, call the constructor with an iterable as
   its positional argument, or use keyword arguments that "shadow" keys in the
   positional argument.

   >>> a = fst([('a', 'b'), ('a', 'c')])
   >>> b = fst({'a': 'b'}, a='c')
   >>> a == b
   True

   When an fst maps a single key to more than one value, subscripting with
   that key will return one arbitrary value.

   >>> d = fst([('a', 'b'), ('a', 'c')])
   >>> d['a'] in {'b', 'c'}
   True

   In addition to the standard Python dictionary operations, fsts provide
   the following:

   .. method:: fst.getall(key)
   .. describe:: t.all[key]

      Return an :class:`fsa` containing all the values corresponding to *key*,
      rather than just one.

   .. method:: fst.query(iterable)
               fst.query(string)

      Treat non-string *iterable* as a collection of keys, or *string* as a single
      key, and return an :class:`fsa` containing all the values which
      correspond to any key.

          >>> d = fst([('I', 'one'), ('II', 'two'), ('III', 'three'), 
          ...              ('IV', 'four'), ('V', 'five')])
          >>> d.query('IV')
          fsa(['four'])
          >>> d.query(set('IV'))
          fsa(['one', 'five'])
          >>> d.query({'I', 'III'})
          fsa(['one', 'three'])

   .. automethod:: keyset

      Return the keys in the current instance as an :class:`fsa` rather than
      an iterator.

   .. automethod:: valueset

      Return the values in the current instance as an :class:`fsa` rather than
      an iterator.

   .. describe:: this + other

      Return an :class:`fst` whose key-value pairs consist of
      key-value pairs from *this* concatenated with key-value pairs from *other*.

      >>> fst({'a': 'b'}) + fst({'c': 'd'})
      fst([('ac', 'bd')])

   .. method:: compose(*others)
   .. describe:: this @ other ...

      |a** Return| an :class:`fst` whose key-value mapping comes from composing
      *this* with each of the others in turn. 

      >>> s = fst({'input': 'intermediate'})
      >>> t = fst({'intermediate': 'output'})
      >>> s @ t
      fst([('input', 'output')])

   .. method:: union(*others)
   .. describe:: this | other ...

      |a** Return| an :class:`fst` with key-value pairs from this and all
      others.
  
   .. method:: priority_union(*others)
   .. describe:: this >> other ...
   .. describe:: ... other << this

      Return an :class:`fst` that behaves like a :class:`collections.ChainMap`,
      chaining together multiple underlying mappings. For each key, the underlying
      mappings are searched in turn, and the key is mapped to the first
      corresponding value that is found. Suppose the mappings *f*, *g*, and
      *h* are as follows::

         >>> f = fst({"a": "1", "b": "1"})
         >>> g = fst({"a": "2",           "c": "2"})
         >>> h = fst({          "b": "3", "c": "3", "d": "3"})

      Then the result of a priority union will be as follows::

         >>> f >> g >> h
         fst([("a", "1"), ("b", "1"), ("c", "2"), ("d", "3")])
         >>> f << g << h
         fst([("a", "2"), ("b", "3"), ("c", "3"), ("d", "3")])
                        
   .. method:: star
               plus

      Return an :class:`fst` whose key-value pairs consist of
      key-value pairs from the current instance concatenated together zero or
      more times (for `star`), or one or more times (for `plus`). 

Shared operations
-----------------

Both :class:`fsa`\ s and :class:`fst`\ s are instances of :class:`fsmcontainer`
and provide the following operations:

.. class:: fsmcontainer

   .. describe:: this + other ...
   .. automethod:: concatenate

   .. automethod:: star

   .. automethod:: plus

   .. describe:: len(a)
   .. automethod:: __len__

      Note that :func:`len` may be quite slow for large finite numbers of
      elements, though it is fast for infinite or small finite numbers. If
      you're getting the length of *a* to compare it to a small number,
      :meth:`len_compare` may be much faster.

   .. method:: len_compare(n, [operator=operator.eq])
   .. automethod:: len_compare(other, [operator=operator.eq])

      If *a* is a large finite acceptor, calculating :literal:`len(a)` can
      be very costly, but testing whether the number of elements is less than,
      equal to, or greater than a small integer *n* is fast. Use this method
      to avoid the costly full calculation of :literal:`len(a)` when *a* is
      not known to be small.

      .. doctest::

         >>> with open('/usr/share/dict/words') as f: # doctest: +SKIP
         ...     a = fsa(f.readlines())               # doctest: +SKIP
         >>> a.len_compare(0)                         # doctest: +SKIP
         False                                        # doctest: +SKIP
         >>> (a & {'supercalifragilisticexpialidocious'}).len_compare(0) # doctest: +SKIP
         True                                         # doctest: +SKIP
      
      Comparison with :literal:`float('inf')` can be used to determine if an
      acceptor is infinite or merely large.

      .. doctest::

         >>> a = fsa({'a'}).star()
         >>> a.len_compare(float('inf'))
         True
         >>> with open('/usr/share/dict/words') as f: # doctest: +SKIP
         ...     a = fsa(f.readlines())               # doctest: +SKIP
         >>> a.len_compare(float('inf'))              # doctest: +SKIP
         False                                        # doctest: +SKIP

      Similarly, if *this* may be large and *other* is known to be small, or
      vice versa, then :literal:`this.len_compare(other)` will be reliably
      fast, while :literal:`len(this) == len(other)` may be quite slow. 


Linguistic applications
-----------------------

If classes of phonemes are given as lists rather than sets or :class:`fsa`\
s, then they can be zipped together and passed to :class:`fst` to create a mapping
from each phoneme in the first class to the corresponding phoneme in the second::

    >>> import fsmcontainers
    >>> k7ichee7 = fsmcontainers.language(
    ...              chars = f.ascii | "á é í ó ú ý ñ ü".split())
    >>> V_short = "a e i o u".split()
    >>> V_long = "aa ee ii oo uu".split()
    >>> V_lengthen = k7ichee7.fst(zip(V_short, V_long))
    >>> V_shorten = V_lengthen.inv
    >>> V_shorten["ii"]
    "i"

Adding an environment with :meth:`between`, :meth:`before`, or :meth:`after`
creates a conditional sound change; using :attr:`anywhere` creates an unconditional
one::

    >>> C = """' b' ch ch' h j k k' l m n o p p'
    ... q q' r s t t' tz tz' w x y""".split()
    >>> V = V_short | V_long
    >>> V_shorten.before(C.star() + V)["nub'aaq'iil"]
    "nub'aq'iil"
    >>> V_shorten.anywhere["nub'aaq'iil"]
    "nub'aq'il"
    >>> V_shorten["nub'aaq'iil"]
    KeyError

Sound changes can be chained together with :literal:`@`. For instance, K'ichee'
has shortening of vowels in nonfinal syllables, followed by the loss of nonfinal
underlying *h* with compensatory lengthening. This can be modeled with three
ordered changes::

    >>> X = C | V
    >>> h_loss = k7ichee7.fst("h", "")
    >>> length_changes = (V_shorten.before(C.star() + V)
    ...                   @ V_lengthen.before("h" + X)
    ...                   @ h_loss.between(V, X))
    >>> length_changes["b'aaq']
    "b'aaq'"
    >>> length_changes["nub'aaq'iil"]
    "nub'aq'iil"
    >>> length_changes["b'eh"]
    "b'eh"
    >>> length_changes["b'ehnaq"]
    "b'eenaq"

The :literal:`<<=` operator is useful for adding exceptions to an existing
sound change or other rule, since it gives its right operand priority over its
left one. For instance, if our corpus contains a few names where shortening,
*h*-loss, and compensatory lengthening shouldn't apply, we can add them in
after the fact like this::

    >>> exceptions = """aaron anahí baalam cooper huehuetenango
    ... ixtahuacán lehnhoff nahualá""".split()
    >>> length_changes <<= exceptions
    >>> length_changes["na b'ehnaq ta ri rak'aalaab' ri a baalam?"]
    "na b'eenaq ta ri rak'alaab' ri a baalam?"

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |a** Return| replace::

   Return 


.. rubric:: Footnotes

.. [#f1] 

   It is easy to imagine infinite sets that cannot be constructed this way. But
   that is the point: the algorithms that make finite state acceptors efficient
   aren't able to handle arbitrary infinite sets. (Whereas we know that they
   *can* handle infinite sets that are constructed using Kleene star,
   intersection, union, subtraction, concatenation, and so on.) 
   
   Another way of putting this is that finite state acceptors have less
   computational power than Turing machines. That is good news in that it
   means we can check strings against them in small finite time. It is bad news
   in that it means there are sets whose membership they can't decide. In some
   domains that tradeoff is acceptable; in others it isn't.
