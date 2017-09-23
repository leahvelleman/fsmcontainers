
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

