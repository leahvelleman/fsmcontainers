from fsmcontainers.fsmcontainers import fsa, fst

vowel = fsa("a e i o u".split())
consonant = fsa("b c d f g h j k l m n p q r s t v w x y z".split())
letter = vowel | consonant

def startswith(s):
    return fsa(s) + letter.star()

def suffix(s):
    return fst(letter.star()) + fst({"": s})

def delprefix(s):
    return fst({s: ""}) + fst(letter.star())

piglatin = fst()
for c in consonant:
    piglatin |= startswith(c) @ suffix(f'{c}ay') @ delprefix(c)

piglatin.write('piglatin.fst')
