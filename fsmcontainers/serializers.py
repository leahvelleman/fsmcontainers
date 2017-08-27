import six
from . import pynini_utils

class Serializer(object):
    """ This class does two jobs: It is a lightweight base class for
    serializers, and its fromPrototype class method takes an object and
    returns the correct serializer for that object. Getting serializers
    via Serializer.fromPrototype guarantees that only one serializer for each
    protocol exists, meaning that we can check that FSMs were serialized
    according to the same protocol by comparing their serializers. 
    
    (We can't just enforce this by making serializer classes singletons,
    because there can be two different protocols implemented by the same
    serializer class.  For instance, 'pairs of strings' and 'triples of
    strings' need different serializers, but both of their serializers will
    belong to the class TupleSerializer.)"""

    serializers = {}

    def __init__(self, prototype):
        pass

    def serialize(self, obj):
        return NotImplemented

    def inflate(self, string):
        return NotImplemented

    def can_serialize(self, string):
        try: 
            pynini_utils.encode(self.serialize(string))
        except ValueError:
            return False
        return True

    @classmethod
    def from_prototype(cls, obj):
        if isinstance(obj, (six.text_type, six.binary_type)):
            key = type(obj)
        else:
            key = (type(obj), len(obj))
        if key not in cls.serializers:
            if isinstance(obj, (six.text_type, six.binary_type)):
                cls.serializers[key] = StringSerializer(obj)
            elif type(obj) == tuple:
                cls.serializers[key] = TupleSerializer(obj)
            else:
                raise TypeError
        return cls.serializers[key]

class StringSerializer(Serializer):

    def __init__(self, prototype):
        pass

    def serialize(self, obj):
        if not isinstance(obj, six.string_types):
            raise ValueError(
                "Non-obj values need to pass through another"
                "codec first")
        if '\0' in obj or '\1' in obj:
            raise ValueError("Pynini doesn't support null bytes in FSMs")
        if not braces_balanced(obj):
            raise ValueError(
                "Unbalanced [ or ] in input. Braces are used to"
                "construct multi-character tokens. If you want a literal"
                "brace character, use '\[' or '\]'")
        return obj

    def inflate(self, string):
        return string

class TupleSerializer(Serializer):

    def __init__(self, prototype):
        self.length = len(prototype)
        self.itemserializers = tuple(Serializer.from_prototype(x) for x in prototype)

    def serialize(self, obj):
        if len(obj) != self.length:
            raise ValueError
        obj = tuple(c.serialize(x) for c, x in zip(self.itemserializers, obj))
        width = max(map(len, obj))
        strings = [field.ljust(width, '\1') for field in obj]
        out = ''.join(''.join(s) for s in zip(*strings))
        return out

    def inflate(self, bts):
        if len(bts) == 0:
            return tuple(['']*self.length)
        seq = [("".join(g)).strip('\1')
               for g in zip(*take_n_by_n(bts, n=self.length))]
        tup = tuple(c.inflate(x) for c, x in zip(self.itemserializers, seq))
        print(bts, seq, tup)
        return tup

def take_n_by_n(t, n):
    args = [iter(t)] * n
    return zip(*args)

def braces_balanced(string):
    brace = False
    for c in string:
        if c == '[':
            if brace:
                return False
            else:
                brace = True
        elif c == ']':
            if not brace:
                return False
            else:
                brace = False
    if not brace:
        return True
    return False
