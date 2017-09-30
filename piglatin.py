import re
from fsmcontainers import fsa, fst

vowel = fsa("a e i o u".split())
consonant = fsa("b c d f g h j k l m n p q r s t v w x y z".split())
punctuation = fsa("- . , ! ? ' \"".split())
character = vowel | consonant | punctuation

onset_re = re.compile("[^aeiouy]+(?=[aeiouy])")
with open("/usr/share/dict/words") as f:
    matches = (onset_re.match(word.lower()) for word in f.readlines())
    onset = {match.group() for match in matches if match is not None}
print(onset)

def onset_matcher(s):
    return fsa(s) + (vowel|fsa("y")) + character.star()

def suffixer(s):
    return fst(character.star()) + fst({"": s}) #HACKY TO CALL FST HERE AND IN DELPREFIX

def prefix_deleter(s):
    return fst({s: ""}) + fst(character.star())

def pig_latinizer(s):
    return onset_matcher(s) @ suffixer(f'-{s}ay') @ prefix_deleter(s)

piglatin = fst().union(pig_latinizer(o) for o in onset) # This oughta be a classmethod

piglatin >>= onset_matcher(fsa("y") + vowel) @ suffixer('-yay') @ prefix_deleter('y')  # HACKY TO CALL FSA HERE

piglatin >>= suffixer('-way')

capitals = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z".split()
lowercase = "a b c d e f g h i j k l m n o p q r s t u v w x y z".split()
downcase = fst(zip(capitals, lowercase)) + character.star()
upcase = fst(zip(lowercase, capitals)) + character.star()

piglatin >>= downcase @ piglatin @ upcase

piglatin += fst(punctuation).star()
piglatin += (fsa(" ") + piglatin).star()

print(piglatin["Do you speak Pig Latin?"])
print(piglatin["Street sprint scrap throat knob schmuck schwa chrome phlegm thwack quit"])
print(piglatin["Yttrium yield sphygmomanometer glycophosphate chrysanthemum rhythm scrying"])
