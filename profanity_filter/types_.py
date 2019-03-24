from dataclasses import dataclass
from typing import Optional, Dict, Collection, Generator, Tuple, List

import spacy.language
from cached_property import cached_property
from hunspell_serializable import HunSpell
from pymorphy2 import MorphAnalyzer


class ProfanityFilterError(Exception):
    pass


@dataclass(frozen=True)
class Word:
    uncensored: str
    censored: str
    original_profane_word: Optional[str] = None

    def __str__(self):
        return self.censored

    @cached_property
    def is_profane(self) -> bool:
        return self.censored != self.uncensored


Words = Dict[str, Word]
Language = Optional[str]
ProfaneWordDictionary = 'OrderedSet[str]'
ProfaneWordDictionaryAcceptable = Collection[str]
ProfaneWordDictionaries = Dict[Language, ProfaneWordDictionary]
ProfaneWordDictionariesAcceptable = Dict[Language, ProfaneWordDictionaryAcceptable]
Languages = 'OrderedSet[Language]'
LanguagesAcceptable = Collection[Language]
Nlps = Dict[Language, spacy.language.Language]
Morphs = Dict[Language, MorphAnalyzer]
Spells = Dict[Language, HunSpell]
Substrings = Generator[Tuple[str, int, int], Tuple[int, int], None]
TextSplittedByLanguage = List[Tuple[Language, str]]


@dataclass(frozen=True)
class Config:
    censor_char: str = '*'
    censor_whole_words: bool = True
    deep_analysis: bool = True
    languages: Tuple[Language, ...] = ('en', )
    max_relative_distance: float = 0.34