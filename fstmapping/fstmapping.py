# pylint: disable=fixme
import functools
import pynini
import pywrapfst
from .codecs import *
from .pynini_utils import clean, m

def binary_op(function, typecheck=None):
    """ Wrap a Pynini two-argument constructive function as a binary
    operation.
    """
    def innerfunction(self, other):
        other = FstContainer.lift(other)
        if typecheck == "product":
            if self.vcodec != other.kcodec:
                raise TypeError
        else:
            if self.kcodec != other.kcodec:
                raise TypeError
            if self.vcodec != other.vcodec:
                raise TypeError
        cls = type(self)
        return cls(fst=function(self.fst, other.fst),
                   kcodec=self.kcodec,
                   vcodec=other.vcodec)
    return innerfunction

def flip_binary(function):
    """ Given a binary operation, produce a right-handed version.
    """
    def innerfunction(self, other):
        other = FstContainer.lift(other)
        return function(other, self)
    return innerfunction

class FstContainer(object):
    """ Base class for container classes backed by FSTs.

    """

    def __init__(self, *args, **kwargs):

        self.inv = None

        if 'parent' in kwargs and isinstance(kwargs['parent'], FstContainer):
            parent = kwargs['parent']
            self.kcodec = parent.vcodec
            self.vcodec = parent.kcodec
            if self.kcodec == self.vcodec:
                self.codec = self.kcodec
            self.fst = pynini.invert(parent.fst)
            self.inv = parent
        elif 'fst' in kwargs and isinstance(kwargs['fst'], pynini.Fst):
            self.kcodec = kwargs['kcodec']
            self.vcodec = kwargs['vcodec']
            if self.kcodec == self.vcodec:
                self.codec = self.kcodec
            self.fst = kwargs['fst']
        else:
            self.defaultconstructor(*args, **kwargs)

    def defaultconstructor(self, *args, **kwargs):
        """ Placeholder for a default constructor method.

        The FstContainer object handles the following special cases, which are
        mainly for internal use:

            * Constructing an inverse FstContainer given a right-side-up one
            * Constructing an FstContainer from a Pynini Fst and codecs

        Subclasses must implement a defaultconstructor() method to handle
        the general case. If the subclass is mimicking a container type,
        its defaultconstructor() method should mimick the constructor for that
        container.
        """
        raise NotImplemented

    @classmethod
    def lift(cls, obj):
        """ Attempt to convert obj to a singleton FstContainer containing obj.

        Most of the work is delegated to subclass lift methods. What
        FstContainer.lift does is choose the right subclass lift method.
        The subclass lift method then calls its own constructor, possibly
        after wrapping the argument in some kind of container.

        For instance:
            * FstContainer.lift(  "a"  )
                 == FstSet.lift(  "a"  )
                      == FstSet( {"a"} )

            * FstContainer.lift(  ("a", "b")  )
                 == FstSet.lift(  ("a", "b")  )
                      == FstSet( {("a", "b")} )

            * FstContainer.lift( {"a": "b"} )
                == FstDict.lift( {"a": "b"} )
                     == FstDict( {"a": "b"} )

        The purpose of lift methods is to make duck typing for binary operators
        more powerful. Given the definitions above and the definition of
        __add__(),

                   FstSet({"a"}) + {"b"}
                == {"a"}         + FstSet({"b"})
                == FstSet({"a"}) + FstSet({"b"}),

                   FstDict({"a": "b"}) + {"c": "d"}
                == {"a": "b"}          + FstDict({"c": "d"})
                == FstDict({"a": "b"}) + FstDict({"c": "d"}),

        and

                   FstSet({"a"}) + FstDict({"b": "c"})
                == {"a"}         + FstDict({"b": "c"})
                == FstSet({"a"}) + {"b": "c"}.
        """

        if isinstance(obj, cls):
            return obj
        if isinstance(obj, set):
            return FstSet(obj)
        return FstSet.lift(obj)
        # Eventually, we will extend this with repeated try/fail for all
        # subclasses.

    def lower(self):
        """ Lower is the inverse of lift. Unlike lift, it will always be
        called on an FstContainer instance, so there is nothing for the base
        class to do. Subclass lower methods should be written so that
        for any x, FstContainer.lift(x).lower() == x (if it doesn't raise an
        error).
        """
        raise NotImplemented

    def singleton(self):
        """ Return True if the FstContainer has exactly one path.
        """
        twoshortest = [p for p in
                       pynini.shortestpath(self.fst, nshortest=2).paths()]
        if len(twoshortest) == 1:
            return True
        return False

    def __hash__(self):
        return hash(self.fst.write_to_string())

    @functools.lru_cache(maxsize=1)
    def sigma(self):
        """ Assemble set of output (value-side) symbols.

        If c is an FstContainer, c.sigma is an FstSet containing each of the
        symbols that appear in values in c. c.sigma can be used as an acceptor
        matching a single character.
        """
        symbols = [clean(pair[1]) for pair in self.fst.output_symbols()]
        return FstSet(symbols)

    @functools.lru_cache(maxsize=1)
    def sigma_star(self):
        """ Assemble infinite set of combinations of output symbols.

        If c is an FstContainer, c.sigma_star is a cyclic (infinite) FstSet
        containing any combination of symbols that appear in values in c.
        c.sigma_star can be used as an acceptor matching a string of any
        length.
        """

        return self.sigma().closure()

    def __len__(self):
        raise TypeError

    def __bool__(self):
        try:
            next(self.fst.paths())
        except pywrapfst.FstArgError:
            return True #FST is cyclic but has successful paths
        except StopIteration:
            return False #FST has no successful paths
        return True #FST is acyclic and has successful paths

    def __iter__(self, limit=None):
        return self.kpaths(limit=limit)

    def __contains__(self, key):
        key = FstSet.lift(key)
        if key.kcodec != self.kcodec:
            raise TypeError
        fst = pynini.compose(key.fst, self.fst)
        return True

    __add__ = binary_op(pynini.concat)
    __radd__ = flip_binary(__add__)
    __or__ = binary_op(pynini.union)
    __ror__ = flip_binary(__or__)
    __mul__ = binary_op(pynini.compose, typecheck="product")
    __rmul__ = flip_binary(__mul__)

    def kpaths(self, limit=None):
        """ Attempt to return an iterator over keys in this FstContainer.

        If an FstContainer is cyclic (infinite), a limit must be specified,
        since Pynini refuses to construct infinite iterators.

        TODO: find a workaround for this.
        """

        fst = self.fst.copy().project(project_output=False)
        if limit is None:
            try:
                stringpaths = fst.paths(
                    input_token_type='symbol',
                    output_token_type='symbol')
            except pywrapfst.FstArgError:
                raise ValueError(
                    "Unlimited iteration over cyclic (i.e. infinite)"
                    "FstContainers is not supported. Specify a positive"
                    "integer as a value for limit.")
        else:
            stringpaths = pynini.shortestpath(fst, nshortest=limit).paths(
                input_token_type='symbol',
                output_token_type='symbol')
        for stringpath in stringpaths:
            yield self.kcodec.unpack(stringpath[0])

    def closure(self):
        """ Return a FstContainer containing the closure of items in this one.
        """
        cls = type(self)
        return cls(fst=pynini.closure(self.fst),
                   kcodec=self.kcodec,
                   vcodec=self.vcodec)

#class FstDict(FstContainer):
#    """ An ordinary one-way mapping backed by an Fst.
#
#    The FstDict() constructor accepts any combination of arguments accepted by
#    the dict() constructor. It checks the types of these arguments against the
#    available codecs and selects the appropriate one if possible.
#
#    Alternatively, FstDict() can be called with a Pynini Fst assigned to the
#    keyword argument `fst`, and (optionally) FstCodec objects assigned to
#    `codec`,
#    `kcodec`, or `vcodec`. If an Fst is specified, any codec left unspecified
#    is
#    taken to be NullCodec(), which leaves input and output strings unchanged.
#
#    """
#
#    def defaultconstructor(self, *args, **kwargs):
#        d = dict(*args, **kwargs)
#        if len(d) == 0:
#            raise ValueError
#        prototype_key = next(iter(d))
#        prototype_value = d[prototype_key]
#        self.kcodec = FstContainer.codec_from_prototype(prototype_key)
#        self.vcodec = FstContainer.codec_from_prototype(prototype_value)
#        self.fst = m((self.kcodec.encode(k), self.vcodec.encode(v))
#                     for k, v in d.items())
#        self.inv = None
#
#    def __mul__(self, other):
#        other = FstSet.lift(other)
#        if self.vcodec != other.kcodec:
#            raise TypeError
#        cls = type(self)
#        return cls(fst=pynini.compose(self.fst, other.fst),
#                   kcodec=self.kcodec,
#                   vcodec=other.vcodec)
#
#    def __getitem__(self, key):
#        key = FstSet.lift(key)
#        form = (key*self.fst).project(project_output=True)
#        if not form:
#            raise KeyError
#        return FstSet.lower(form)
#
#    # TODO: memoize, make sure we're giving out COPIES of the iterator so
#    # we don't give out a half-eaten one by mistake
#    def keys(self, limit=None):
#        for w in upper_words(self.fst, limit=limit):
#            yield self.kcodec.decode(w)
#
#    def values(self, limit=None):
#        for w in lower_words(self.fst, limit=limit):
#            yield self.vcodec.decode(w)
#
#    # These are defined in terms of methods that have already had their
#    # encodeers and decoders applied, so they don't need to call encode()
#    # and decode() themselves themselves:
#
#    def __iter__(self):
#        for word in self.keys():
#            yield word, self[word]
#
#    def items(self):
#        return self.__iter__
#
#
#class FstBidict(FstDict):
#
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#        if self.inv is None:
#            cls = type(self)
#            self.inv = cls(parent=self)
#
#    def __invert__(self):
#        return self.inv

class FstSet(FstContainer):

    def defaultconstructor(self, *args, **kwargs):
        as_set = set(*args, **kwargs)
        try:
            prototype_item = next(iter(as_set))
        except StopIteration:
            prototype_item = ''
        self.codec = self.kcodec = self.vcodec =\
                FstCodec.from_prototype(prototype_item)
        self.fst = m(((self.codec.encode(item),
                       self.codec.encode(item)) for item in as_set))

    def __hash__(self):
        return hash(self.fst.write_to_string() + str(self.codec).encode())

    @classmethod
    def lift(cls, obj):
        if isinstance(obj, FstSet):
            return obj
        if isinstance(obj, set):
            return FstSet(obj)
        if isinstance(obj, str):
            return FstSet({obj})
        if isinstance(obj, tuple):
            return FstSet({obj})

    def lower(self):
        if self.singleton():
            out, _, _ = next(self.fst.paths(input_token_type="symbol",
                                            output_token_type="symbol"))
            return self.codec.unpack(out)
        return self

    def __eq__(self, other):
        if self.kcodec != other.kcodec:
            raise TypeError
        if self.vcodec != other.vcodec:
            raise TypeError
        return pynini.equivalent(self.fst.optimize(), other.fst.optimize())
