import nltk
from nltk.corpus import words
from nltk.corpus import wordnet
import re

def spell_check(self):
    nltk.download('wordnet')
    nltk.download('words')
    content = self.text.get("1.0",'end-1c')
    wn_lemmas = set(wordnet.all_lemma_names())
    for tag in self.text.tag_names():
        self.text.tag_delete(tag)
    self.text.tag_configure('spell_error', underline=True, underlinefg='red')
    fails = 0
    for word in content.split(' '):
        word_to_check = re.sub(r'[^\w]', '', word.lower()).lower()
        if wordnet.synsets(word_to_check) == [] :
            if word_to_check not in words.words():
                if not any(True for _ in re.finditer('^[0-9]*$', word_to_check)):
                    position = content.find(word)
                    self.text.tag_add('spell_error', f'1.{position}', f'1.{position + len(word)}')
                    fails += 1
    return fails
