import six
from .pynini_utils import clean, braces_balanced

class FstCodec(object):

    codecs = {}

    def __init__(self, prototype):
        pass

    def pack(self, obj):
        return FinalCodec.encode(self.encode(obj))

    def unpack(self, string):
        return self.decode(FinalCodec.decode(string))

    def can_pack(self, string):
        try: 
            self.pack(string)
        except ValueError:
            return False
        return True

    @classmethod
    def from_prototype(cls, obj):
        if isinstance(obj, (six.text_type, six.binary_type)):
            key = type(obj)
        else:
            key = (type(obj), len(obj))
        if key not in cls.codecs:
            if isinstance(obj, (six.text_type, six.binary_type)):
                cls.codecs[key] = StringCodec(obj)
            elif type(obj) == tuple:
                cls.codecs[key] = TupleCodec(obj)
            else:
                raise TypeError
        return cls.codecs[key]

class FinalCodec(FstCodec):

    def __init__(self, *args, **kwargs):
        pass

    def encode(self, string):
        if not isinstance(string, six.string_types):
            raise ValueError(
                "Non-string values need to pass through another"
                "codec first")
        if '\0' in string or '\1' in string:
            raise ValueError("Pynini doesn't support null bytes in FSMs")
        if not braces_balanced(string):
            raise ValueError(
                "Unbalanced [ or ] in input. Braces are used to"
                "construct multi-character tokens. If you want a literal"
                "brace character, use '\[' or '\]'")
        return string

    def decode(self, string):
        return clean(string)

FinalCodec = FinalCodec()

class StringCodec(FstCodec):

    def __init__(self, prototype):
        pass

    def encode(self, obj):
        return obj

    def decode(self, obj):
        return obj

class TupleCodec(FstCodec):

    def __init__(self, prototype):
        self.length = len(prototype)
        self.itemcodecs = tuple(FstCodec.from_prototype(x) for x in prototype)

    def encode(self, obj):
        if len(obj) != self.length:
            raise ValueError
        obj = tuple(c.encode(x) for c, x in zip(self.itemcodecs, obj))
        width = max(map(len, obj))
        strings = [field.ljust(width, '\1') for field in obj]
        out = ''.join(''.join(s) for s in zip(*strings))
        return out

    def decode(self, bts):
        if len(bts) == 0:
            return tuple(['']*self.length)
        seq = [("".join(g)).strip('\1')
               for g in zip(*take_n_by_n(bts, n=self.length))]
        tup = tuple(c.decode(x) for c, x in zip(self.itemcodecs, seq))
        print(bts, seq, tup)
        return tup

def take_n_by_n(t, n):
    args = [iter(t)] * n
    return zip(*args)
