from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Collection, Generator, Tuple, List, FrozenSet

import spacy.language
from cached_property import cached_property
from hunspell_serializable import HunSpell
from pydantic import BaseModel
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


class AnalysisType(Enum):
    DEEP = 'deep'
    MORPHOLOGICAL = 'morphological'
    MULTILINGUAL = 'multilingual'


Words = Dict[str, Word]
AnalysesTypes = FrozenSet[AnalysisType]
Language = Optional[str]
ProfaneWordDictionary = 'OrderedSet[str]'
ProfaneWordDictionaryAcceptable = Collection[str]
ProfaneWordDictionaries = Dict[Language, ProfaneWordDictionary]
ProfaneWordDictionariesAcceptable = Optional[Dict[Language, ProfaneWordDictionaryAcceptable]]
Languages = 'OrderedSet[Language]'
LanguagesAcceptable = Collection[Language]
Nlps = Dict[Language, spacy.language.Language]
Morphs = Dict[Language, MorphAnalyzer]
Spells = Dict[Language, HunSpell]
Substrings = Generator[Tuple[str, int, int], Tuple[int, int], None]
TextSplittedByLanguage = List[Tuple[Language, str]]


# noinspection PyTypeChecker
class Config(BaseModel):
    analyses: List[AnalysisType] = list(AnalysisType)
    cache_redis_connection_url: Optional[str] = None
    censor_char: str = '*'
    censor_whole_words: bool = True
    languages: List[Language] = ['en']
    max_relative_distance: float = 0.34
