import re
from collections import defaultdict
from contextlib import suppress, contextmanager
from copy import deepcopy
from itertools import chain
from math import floor
from pathlib import Path
from typing import Dict, Union, List, Tuple, Set, Collection, ContextManager, Optional

import poetry_version
import spacy
import spacy.attrs
import spacy.language
import spacy.tokens
from cached_property import cached_property
from more_itertools import substrings_indexes
from ordered_set import OrderedSet
from redis import Redis

from profanity_filter import spacy_utlis
from profanity_filter.config import Config, DEFAULT_CONFIG
from profanity_filter.spacy_component import SpacyProfanityFilterComponent
from profanity_filter.types_ import (Words, Language, ProfaneWordDictionaries, ProfaneWordDictionariesAcceptable,
                                     Languages, LanguagesAcceptable, Nlps, Morphs, Spells, Substrings,
                                     TextSplittedByLanguage, ProfanityFilterError, Word, AnalysisType, AnalysesTypes)


class DummyHunSpell:
    def __init__(self, *args):
        pass

    @staticmethod
    def spell(word: str) -> str:
        return word

    @staticmethod
    def stem(word: str) -> List[bytes]:
        return [word.encode('utf8')]

    @staticmethod
    def get_dic_encoding():
        return 'utf8'


class DummyMorphAnalyzer:
    def __init__(self):
        pass

    @staticmethod
    def parse(word):
        class ParseResult:
            def __init__(self):
                self.normal_form = word

        return [ParseResult()]


# Defining variables in case of unavailable analyses
HunSpell = DummyHunSpell
HunSpellError = None
Trie = None
MorphAnalyzer = DummyMorphAnalyzer


_available_analyses_list = []

with suppress(ImportError):
    from profanity_filter.analysis.deep import *
    _available_analyses_list.append(AnalysisType.DEEP)

with suppress(ImportError):
    from profanity_filter.analysis.morphological import *
    _available_analyses_list.append(AnalysisType.MORPHOLOGICAL)

with suppress(ImportError):
    from profanity_filter.analysis.multilingual import *
    _available_analyses_list.append(AnalysisType.MULTILINGUAL)

AVAILABLE_ANALYSES: AnalysesTypes = frozenset(_available_analyses_list)


APP_NAME = 'profanity-filter'
__version__ = poetry_version.extract(source_file=__file__)


class ProfanityFilter:
    def __init__(self,
                 languages: LanguagesAcceptable = tuple(DEFAULT_CONFIG.languages),
                 *,
                 analyses: AnalysesTypes = frozenset(DEFAULT_CONFIG.analyses),
                 cache_redis_connection_url: Optional[str] = None,
                 censor_char: str = DEFAULT_CONFIG.censor_char,
                 censor_whole_words: bool = DEFAULT_CONFIG.censor_whole_words,
                 custom_profane_word_dictionaries: ProfaneWordDictionariesAcceptable = None,
                 extra_profane_word_dictionaries: ProfaneWordDictionariesAcceptable = None,
                 max_relative_distance: float = DEFAULT_CONFIG.max_relative_distance,
                 morphs: Optional[Morphs] = None,
                 nlps: Optional[Nlps] = None,
                 spells: Optional[Spells] = None,
                 ):
        # Path to data dir
        self._BASE_DIR = Path(__file__).absolute().parent
        self._DATA_DIR: Path = self._BASE_DIR / 'data'

        self._MAX_MAX_DISTANCE = 3

        # Set dummy values to satisfy the linter (they will be overwritten in `config`)
        self._analyses: AnalysesTypes = frozenset()
        self._cache_clearing_disabled: bool = False
        self._cache_redis: Optional[Redis] = None
        self._cache_redis_connection_url: Optional[str] = None
        self._censor_char: str = ''
        self._censor_whole_words: bool = False
        self._custom_profane_word_dictionaries: ProfaneWordDictionaries = {}
        self._extra_profane_word_dictionaries: ProfaneWordDictionaries = {}
        self._languages: Languages = OrderedSet()
        self._max_relative_distance: float = 0.0
        self._morphs: Morphs = {}
        self._nlps: Nlps = {}
        self._profane_word_dictionary_files: Dict[Language, Path] = {}
        self._spells: Spells = {}

        # For Levenshtein automata
        self._alphabet = set()
        self._trie = {}

        # Cache of censored words
        self._censored_words: Words = {}

        # Cache of words with no profanity inside that is generated after censoring
        # (include words that are not in the dictionary)
        self._words_with_no_profanity_inside: Set[str] = set()

        # What to be censored - should not be modified by user
        self._censor_dictionaries: ProfaneWordDictionaries = {}

        with self._disabled_cache_clearing():
            self.config(
                languages=languages,
                analyses=analyses,
                cache_redis_connection_url=cache_redis_connection_url,
                censor_char=censor_char,
                censor_whole_words=censor_whole_words,
                custom_profane_word_dictionaries=custom_profane_word_dictionaries,
                extra_profane_word_dictionaries=extra_profane_word_dictionaries,
                max_relative_distance=max_relative_distance,
                morphs=morphs,
                nlps=nlps,
                spells=spells,
            )

        self.clear_cache()

    def config(self,
               languages: LanguagesAcceptable = tuple(DEFAULT_CONFIG.languages),
               *,
               analyses: AnalysesTypes = frozenset(DEFAULT_CONFIG.analyses),
               cache_redis_connection_url: Optional[str] = DEFAULT_CONFIG.cache_redis_connection_url,
               censor_char: str = DEFAULT_CONFIG.censor_char,
               censor_whole_words: bool = DEFAULT_CONFIG.censor_whole_words,
               custom_profane_word_dictionaries: ProfaneWordDictionariesAcceptable = None,
               extra_profane_word_dictionaries: ProfaneWordDictionariesAcceptable = None,
               max_relative_distance: float = DEFAULT_CONFIG.max_relative_distance,
               morphs: Optional[Morphs] = None,
               nlps: Optional[Nlps] = None,
               spells: Optional[Spells] = None,
               ):
        self.analyses = analyses
        self.cache_redis_connection_url = cache_redis_connection_url
        self.censor_char = censor_char
        self.censor_whole_words = censor_whole_words
        self.custom_profane_word_dictionaries = custom_profane_word_dictionaries
        self.extra_profane_word_dictionaries = extra_profane_word_dictionaries
        self.max_relative_distance = max_relative_distance
        self._set_languages(languages, load_morphs=morphs is None, load_nlps=nlps is None, load_spells=spells is None)
        if morphs is not None:
            self.morphs = morphs
        if nlps is not None:
            self.nlps = nlps
        if spells is not None:
            self.spells = spells

    @classmethod
    def from_config(cls, config: Config) -> 'ProfanityFilter':
        return cls(
            languages=config.languages,
            analyses=frozenset(config.analyses),
            cache_redis_connection_url=config.cache_redis_connection_url,
            censor_char=config.censor_char,
            censor_whole_words=config.censor_whole_words,
            max_relative_distance=config.max_relative_distance,
        )

    @classmethod
    def from_yaml(cls, path: Union[Path, str]) -> 'ProfanityFilter':
        return cls.from_config(Config.from_yaml(path))

    def censor(self, text: str) -> str:
        """Returns text with any profane words censored"""
        return self._censor(text=text, return_bool=False)

    def censor_word(self, word: Union[str, spacy.tokens.Token], language: Language = None) -> Word:
        """Returns censored word"""
        word = self._make_spacy_token(language=language, word=word)
        return self._censor_word(language=language, word=word)

    def is_clean(self, text: str) -> bool:
        """Returns True if text doesn't contain any profane words, False otherwise"""
        return not self.is_profane(text=text)

    def is_profane(self, text: str) -> bool:
        """Returns True if input_text contains any profane words, False otherwise"""
        return self._censor(text=text, return_bool=True)

    @cached_property
    def spacy_component(self, language: Language = None) -> SpacyProfanityFilterComponent:
        nlp = self._get_nlp(language)
        [language] = [language for language, nlp_ in self.nlps.items() if nlp_ == nlp]
        return SpacyProfanityFilterComponent(profanity_filter=self, nlp=nlp, language=language)

    @property
    def analyses(self) -> AnalysesTypes:
        return self._analyses

    @analyses.setter
    def analyses(self, value: Collection[AnalysisType]) -> None:
        self._analyses = AVAILABLE_ANALYSES.intersection(value)
        self.clear_cache()

    @property
    def cache_redis_connection_url(self) -> Optional[str]:
        return self._cache_redis_connection_url

    @cache_redis_connection_url.setter
    def cache_redis_connection_url(self, value: Optional[str]) -> None:
        self._cache_redis_connection_url = value
        if value is not None:
            self._cache_redis = Redis.from_url(value)

    @property
    def censor_char(self) -> str:
        """What to censor the words with"""
        return self._censor_char

    @censor_char.setter
    def censor_char(self, value: str) -> None:
        """Replaces the original censor char '*' with value"""
        if len(value) != 1:
            raise ValueError("Censor char must be str of length 1")
        self._censor_char = value
        self.clear_cache()

    @property
    def censor_whole_words(self) -> bool:
        return self._censor_whole_words

    @censor_whole_words.setter
    def censor_whole_words(self, value: bool) -> None:
        self._censor_whole_words = value
        self.clear_cache()

    @property
    def custom_profane_word_dictionaries(self) -> ProfaneWordDictionaries:
        """If defined, use this instead of _censor_lists"""
        return self._custom_profane_word_dictionaries

    @custom_profane_word_dictionaries.setter
    def custom_profane_word_dictionaries(self, value: ProfaneWordDictionariesAcceptable) -> None:
        if value is None:
            value = {}
        else:
            value = {language: OrderedSet(custom_censor_dictionary)
                     for language, custom_censor_dictionary in value.items()}
        self._custom_profane_word_dictionaries = defaultdict(lambda: OrderedSet(), **value)
        self.clear_cache()

    @property
    def extra_profane_word_dictionaries(self) -> ProfaneWordDictionaries:
        """Words to be used in conjunction with _censor_dictionaries"""
        return self._extra_profane_word_dictionaries

    @extra_profane_word_dictionaries.setter
    def extra_profane_word_dictionaries(self, value: ProfaneWordDictionariesAcceptable) -> None:
        if value is None:
            value = {}
        else:
            value = {language: OrderedSet(extra_profane_word_dictionary)
                     for language, extra_profane_word_dictionary in value.items()}
        self._extra_profane_word_dictionaries = defaultdict(lambda: OrderedSet(), **value)
        self.clear_cache()

    @property
    def languages(self) -> Languages:
        """Languages"""
        return self._languages

    @languages.setter
    def languages(self, value: LanguagesAcceptable) -> None:
        self._set_languages(value)

    @cached_property
    def languages_str(self) -> str:
        return ', '.join(self.languages)

    @property
    def max_relative_distance(self) -> float:
        """Max relative distance to profane words"""
        return self._max_relative_distance

    @max_relative_distance.setter
    def max_relative_distance(self, value: float) -> None:
        self._max_relative_distance = value
        self.clear_cache()

    @property
    def morphs(self) -> Morphs:
        return self._morphs

    @morphs.setter
    def morphs(self, value: Optional[Morphs]) -> None:
        if AnalysisType.MORPHOLOGICAL in self.analyses:
            self.clear_cache()
            if value is not None:
                self._morphs = value
            else:
                self._morphs = {}
                for language in self.languages:
                    with suppress(ValueError):
                        self._morphs[language] = MorphAnalyzer(lang=language)
                if not self._morphs:
                    self.analyses -= {AnalysisType.MORPHOLOGICAL}

    @property
    def nlps(self) -> Nlps:
        return self._nlps

    @nlps.setter
    def nlps(self, value: Optional[Nlps]) -> None:
        self.clear_cache()
        if value is not None:
            self._nlps = value
        else:
            self._nlps = {}
            for language in self.languages:
                with suppress(OSError):
                    self._nlps[language] = spacy.load(language, disable=['parser', 'ner'])
                    self._nlps[language].add_pipe(self.spacy_component, last=True)
            if not self._nlps:
                raise ProfanityFilterError(f"Couldn't load Spacy model for any of languages: {self.languages_str}")

    @cached_property
    def profane_word_dictionaries(self) -> ProfaneWordDictionaries:
        """Gets profane word dictionaries"""
        if self.custom_profane_word_dictionaries:
            result = deepcopy(self.custom_profane_word_dictionaries)
        else:
            self._load_profane_word_dictionaries()
            result = deepcopy(self._censor_dictionaries)

        for language in self.languages.intersection(list(self.extra_profane_word_dictionaries.keys())):
            result[language] |= self.extra_profane_word_dictionaries[language]

        if AnalysisType.DEEP in self.analyses:
            self._trie = {language: Trie(words=result[language], alphabet=self._alphabet)
                          for language in self.languages}
            for length in range(self._MAX_MAX_DISTANCE + 1):
                generate_automaton_to_file(length)

        return result

    @property
    def spells(self) -> Spells:
        return self._spells

    @spells.setter
    def spells(self, value: Optional[Spells]) -> None:
        if AnalysisType.DEEP in self.analyses:
            self.clear_cache()
            if value is not None:
                self._spells = value
            else:
                self._spells = {}
                for language in self._languages:
                    with suppress(HunSpellError):
                        self._spells[language] = HunSpell(self._DATA_DIR / f'{language}.dic',
                                                          self._DATA_DIR / f'{language}.aff')
                if not self._spells:
                    self.analyses -= {AnalysisType.DEEP}

    def clear_cache(self) -> None:
        if self._cache_clearing_disabled:
            return

        self._update_profane_word_dictionary_files()
        self._update_profane_word_dictionaries()
        self._clear_words_cache()

    def restore_profane_word_dictionaries(self) -> None:
        """ Clears all custom censor lists """
        self.custom_profane_word_dictionaries = None
        self.extra_profane_word_dictionaries = None

    @contextmanager
    def _disabled_cache_clearing(self) -> ContextManager[None]:
        self._cache_clearing_disabled = True
        yield
        self._cache_clearing_disabled = False

    def _clear_words_cache(self):
        self._censored_words = {}
        self._words_with_no_profanity_inside = set()
        if self._cache_redis is not None:
            self._cache_redis.flushdb()

    def _update_languages_str(self) -> None:
        if self._cache_clearing_disabled:
            return

        with suppress(KeyError):
            del self.__dict__['languages_str']
        _ = self.languages_str

    def _set_languages(self, value: LanguagesAcceptable, load_morphs: bool = True, load_nlps: bool = True,
                       load_spells: bool = True) -> None:
        self._languages = OrderedSet(value)
        self._update_languages_str()
        if load_morphs:
            self.morphs = None
        if load_nlps:
            self.nlps = None
        if load_spells:
            self.spells = None
        self.clear_cache()

    def _update_profane_word_dictionary_files(self):
        # Paths to profane word dictionaries
        self._profane_word_dictionary_files = {}
        for language in self.languages:
            profane_word_file = self._DATA_DIR / f'{language}_profane_words.txt'
            if profane_word_file.is_file():
                self._profane_word_dictionary_files[language] = profane_word_file
        if not self._profane_word_dictionary_files:
            raise ProfanityFilterError(f"Couldn't load profane words for any of languages: {self.languages_str}")

    def _update_profane_word_dictionaries(self) -> None:
        if self._cache_clearing_disabled:
            return

        with suppress(KeyError):
            del self.__dict__['profane_word_dictionaries']
        _ = self.profane_word_dictionaries

    def _load_profane_word_dictionaries(self) -> None:
        """Loads the dictionaries of profane words from files"""
        self._update_profane_word_dictionary_files()
        self._censor_dictionaries = defaultdict(lambda: OrderedSet())
        for language, words_file in self._profane_word_dictionary_files.items():
            with open(str(words_file)) as f:
                self._censor_dictionaries[language] = OrderedSet(line.strip() for line in f.readlines())

    def _get_max_distance(self, length: int) -> float:
        return min(self._MAX_MAX_DISTANCE, floor(self.max_relative_distance * length))

    def _make_spacy_token(self, language: Language, word: str) -> spacy.tokens.Token:
        return spacy_utlis.make_token(nlp=self._get_nlp(language), word=word)

    def _drop_fully_censored_words(self, substrings: Substrings) -> Substrings:
        return ((word, start, finish)
                for word, start, finish in substrings
                if not all(char == self.censor_char for char in word))

    @staticmethod
    def _drop_substrings(substrings: Substrings) -> Substrings:
        drop_intervals = set()
        for word, start, finish in substrings:
            if all(start < drop_start or finish > drop_finish for drop_start, drop_finish in drop_intervals):
                result = (word, start, finish)
                drop = yield result
                drop_start, drop_finish = drop
                if drop_start is not None and drop_finish is not None:
                    drop_intervals.add((drop_start, drop_finish))

    def _generate_fully_censored_word(self, word: Union[str, spacy.tokens.Token]) -> str:
        with suppress(AttributeError):
            word = word.text
        return len(word) * self.censor_char

    def _generate_partly_censored_word(self, word: Union[str, spacy.tokens.Token], profane_word: str) -> str:
        def is_delete_or_insert(opcode):
            return opcode[0] in ('delete', 'insert')

        # noinspection PyShadowingNames
        def find_word_part(word: str, word_part: str) -> str:
            word_to_word_part_opcodes = Levenshtein.opcodes(word, word_part)
            word_part_in_word_start = (
                word_to_word_part_opcodes[0][2] if is_delete_or_insert(word_to_word_part_opcodes[0]) else 0)
            word_part_in_word_finish = (
                word_to_word_part_opcodes[-1][1] if is_delete_or_insert(word_to_word_part_opcodes[-1]) else len(word))
            return word[word_part_in_word_start:word_part_in_word_finish]

        with suppress(AttributeError):
            word = word.text

        word_part_for_censoring = find_word_part(word.lower(), profane_word)
        return regex.sub(pattern=re.escape(word_part_for_censoring),
                         repl=self._generate_fully_censored_word(word=word_part_for_censoring),
                         string=word,
                         flags=regex.IGNORECASE)

    def _get_nlp(self, language: Language) -> spacy.language.Language:
        # noinspection PyTypeChecker
        languages = OrderedSet([language]) | self.languages
        for nlp_language in languages:
            with suppress(KeyError):
                return self.nlps[nlp_language]

    def _parse(self,
               language: Language,
               text: str,
               use_profanity_filter: bool = True) -> spacy.tokens.Doc:
        nlp = self._get_nlp(language)
        return spacy_utlis.parse(nlp=nlp, text=text, language=language, use_profanity_filter=use_profanity_filter)

    def _get_spells(self, language: Language) -> 'OrderedSet[HunSpell]':
        result = OrderedSet([DummyHunSpell()])
        if AnalysisType.DEEP not in self.analyses:
            return result
        if language is None:
            return OrderedSet(self.spells.values())
        # noinspection PyTypeChecker
        languages = OrderedSet([language]) | self.languages
        for language in languages:
            with suppress(KeyError):
                result = OrderedSet([self.spells[language]])
                break
        return result

    def _stems(self, language: Language, word: str) -> 'OrderedSet[str]':
        spells = self._get_spells(language=language)
        try:
            return OrderedSet([stem_bytes.decode(spell.get_dic_encoding())
                               for spell in spells for stem_bytes in spell.stem(word)])
        except UnicodeEncodeError:
            return OrderedSet()

    def _normal_forms(self, language: Language, word: str) -> 'OrderedSet[str]':
        morph = DummyMorphAnalyzer
        if AnalysisType.MORPHOLOGICAL in self.analyses:
            # noinspection PyTypeChecker
            languages = OrderedSet([language]) | self.languages
            for language in languages:
                with suppress(KeyError):
                    morph = self.morphs[language]
                    break
        return OrderedSet([morph.parse(word=word)[0].normal_form])

    def _lemmas(self, language: Language, word: Union[str, spacy.tokens.Token]) -> 'OrderedSet[str]':
        result = OrderedSet()
        if not word:
            return result
        word = self._make_spacy_token(language=language, word=word)
        spacy_lemma = word.lemma_
        result.add(word.text)
        spacy_lemma = spacy_lemma.lower() if spacy_lemma != '-PRON-' else word.lower_
        result.add(spacy_lemma)
        result |= self._stems(language=language, word=word.text)
        result |= self._normal_forms(language=language, word=word.text)
        return result

    def _is_dictionary_word(self, language: Language, word: str) -> bool:
        try:
            return any(spell.spell(word) for spell in self._get_spells(language=language))
        except UnicodeEncodeError:
            return False

    def _keep_only_letters_or_dictionary_word(self, language: Language, word: Union[str, spacy.tokens.Token]) -> str:
        with suppress(AttributeError):
            word = word.text
        if language is None:
            language = self.languages[0]
        if AnalysisType.DEEP in self.analyses and self._is_dictionary_word(language=language, word=word):
            return word
        else:
            return ''.join(regex.findall(r'\p{letter}', word))

    def _get_words_with_no_profanity_inside(self) -> Set[str]:
        if self._cache_redis is None:
            return self._words_with_no_profanity_inside
        else:
            return {word.decode('utf8') for word in self._cache_redis.smembers('_words_with_no_profanity_inside')}

    def _has_no_profanity(self, words: Collection[str]) -> bool:
        return any(word in word_with_no_profanity_inside
                   for word in words
                   for word_with_no_profanity_inside in self._get_words_with_no_profanity_inside())

    def _get_trie(self, language: Language) -> Trie:
        result = None
        # noinspection PyTypeChecker
        languages = OrderedSet([language]) | self.languages
        for language in languages:
            with suppress(KeyError):
                result = self._trie[language]
                break
        return result

    def _is_profane_word(self, language: Language, word: str) -> bool:
        profane_word_dictionaries = (self.profane_word_dictionaries.values()
                                     if language is None else
                                     [self.profane_word_dictionaries[language]])
        return any(word in profane_word_dictionary for profane_word_dictionary in profane_word_dictionaries)

    def _get_censored_word(self, word: spacy.tokens.Token) -> Optional[Word]:
        if self._cache_redis is None:
            return self._censored_words.get(word.text)
        else:
            d = self._cache_redis.hgetall(word.text)
            if not d:
                return None
            uncensored, censored, original_profane_word = d[b'uncensored'], d[b'censored'], d[b'original_profane_word']
            if not original_profane_word:
                original_profane_word = None
            return Word(uncensored=uncensored, censored=censored, original_profane_word=original_profane_word)

    def _save_censored_word(self, word: Word) -> None:
        if self._cache_redis is None:
            self._censored_words[word.uncensored] = word
        else:
            d = dict(word)
            if not word.original_profane_word:
                d['original_profane_word'] = ''
            self._cache_redis.hmset(word.uncensored, d)

    def _censor_word_part(self, language: Language, word: spacy.tokens.Token) -> Tuple[Word, bool]:
        """
        :return: Tuple of censored word and flag of no profanity inside
        """
        lemmas = self._lemmas(word=word, language=language)
        if AnalysisType.DEEP in self.analyses:
            lemmas_only_letters = OrderedSet([
                self._keep_only_letters_or_dictionary_word(language=language, word=lemma) for lemma in lemmas])
            if lemmas_only_letters != lemmas:
                lemmas_only_letters = [
                    *chain(*(self._lemmas(word=lemma, language=language) for lemma in lemmas_only_letters))]
                lemmas.update(lemmas_only_letters)
        if self._has_no_profanity(lemmas):
            return Word(uncensored=word.text, censored=word.text), True
        censored_word = self._get_censored_word(word)
        if censored_word is not None:
            return censored_word, False
        for lemma in lemmas:
            if self._is_profane_word(language=language, word=lemma):
                if self.censor_whole_words:
                    censored = self._generate_fully_censored_word(word=word)
                else:
                    censored = self._generate_partly_censored_word(word=word, profane_word=lemma)
                censored_word = Word(uncensored=word.text, censored=censored, original_profane_word=lemma)
                self._save_censored_word(censored_word)
                return censored_word, False
        if AnalysisType.DEEP in self.analyses:
            for lemma in lemmas:
                if self._is_dictionary_word(language=language, word=lemma):
                    return Word(uncensored=word.text, censored=word.text), True
                automaton = LevenshteinAutomaton(tolerance=self._get_max_distance(len(lemma)),
                                                 query_word=lemma,
                                                 alphabet=self._alphabet)
                matching_bad_words = trie_automaton_intersection(automaton=automaton,
                                                                 trie=self._get_trie(language=language),
                                                                 include_error=False)
                if matching_bad_words:
                    bad_word = matching_bad_words[0]
                    if self.censor_whole_words:
                        censored = self._generate_fully_censored_word(word=word)
                    else:
                        censored = self._generate_partly_censored_word(word=word, profane_word=bad_word)
                    censored_word = Word(uncensored=word.text, censored=censored, original_profane_word=bad_word)
                    self._save_censored_word(censored_word)
                    return censored_word, False
        return Word(uncensored=word.text, censored=word.text), False

    def _save_word_with_no_profanity_inside(self, word: spacy.tokens.Token) -> None:
        if self._cache_redis is None:
            self._words_with_no_profanity_inside.add(word.text)
        else:
            self._cache_redis.sadd('_words_with_no_profanity_inside', word.text)

    def _censor_word(self, language: Language, word: spacy.tokens.Token) -> Word:
        """Returns censored word"""
        censored_word_prev = None
        censored_word = Word(uncensored=word.text, censored=word.text)
        while censored_word != censored_word_prev:
            censored_word_prev = censored_word
            substrings = (
                self._drop_substrings(
                    self._drop_fully_censored_words(
                        substrings_indexes(censored_word_prev.censored, reverse=True)
                    )
                )
            )
            no_profanity_start, no_profanity_finish = None, None
            try:
                substring = next(substrings)
                censored_part, start, finish = substring
            except StopIteration:
                break
            while True:
                try:
                    censored_part = self._make_spacy_token(language=language, word=censored_part)
                    censored_censored_part, no_profanity_inside = self._censor_word_part(language=language,
                                                                                         word=censored_part)
                    if no_profanity_inside:
                        no_profanity_start, no_profanity_finish = start, finish
                    if censored_censored_part.censored != censored_part.text:
                        if self.censor_whole_words:
                            censored = self._generate_fully_censored_word(word=word)
                        else:
                            censored = censored_word_prev.censored.replace(
                                censored_part.text, censored_censored_part.censored)
                        censored_word = Word(
                            uncensored=word.text,
                            censored=censored,
                            original_profane_word=censored_censored_part.original_profane_word,
                        )
                    # Stop after first iteration (with word part equal word) when deep analysis is disabled
                    # Also stop if word was partly censored
                    if AnalysisType.DEEP not in self.analyses or (censored_word != censored_word_prev):
                        break
                    censored_part, start, finish = substrings.send((no_profanity_start, no_profanity_finish))
                except StopIteration:
                    break
        if censored_word.censored == word.text:
            if AnalysisType.DEEP in self.analyses and not self._is_dictionary_word(language=language, word=word.text):
                self._save_word_with_no_profanity_inside(word)
        else:
            self._save_censored_word(censored_word)
        return censored_word

    def _detect_languages(self, text: str) -> Languages:
        fallback_language = self.languages[0]
        fallback_result = OrderedSet([fallback_language])
        if AnalysisType.MULTILINGUAL in self.analyses:
            polyglot_output = polyglot.detect.Detector(text, quiet=True)
            result = OrderedSet([language.code for language in polyglot_output.languages if language.code != 'un'])
            if not result:
                result = fallback_result
        else:
            result = fallback_result
        result = result.intersection(self.languages)
        return result

    @staticmethod
    def _merge_by_language(parts: TextSplittedByLanguage) -> TextSplittedByLanguage:
        result = []
        language = parts[0][0]
        merged = parts[0][1]
        i = 1
        while i < len(parts):
            if parts[i][0] != language:
                result.append((language, merged))
                language = parts[i][0]
                merged = parts[i][1]
            else:
                merged += parts[i][1]
            i += 1
        result.append((language, merged))
        return result

    def _split_by_language(self, text: str) -> TextSplittedByLanguage:
        languages = self._detect_languages(text=text)
        tokens = re.split(r'(\W)', text)
        if len(languages) == 0:
            return [(None, text)]
        elif len(languages) == 1 or len(tokens) <= 1:
            # noinspection PyTypeChecker
            return [(languages[0], text)]
        else:
            middle_index = len(tokens) // 2
            left_text, right_text, = ''.join(tokens[:middle_index]), ''.join(tokens[middle_index:])
            left = self._split_by_language(text=left_text)
            right = self._split_by_language(text=right_text)
            return ProfanityFilter._merge_by_language(left + right)

    @staticmethod
    def _replace_token(text: str, old: spacy.tokens.Token, new: str) -> str:
        return text[:old.idx] + new + text[old.idx + len(old.text):]

    # noinspection PyProtectedMember
    def _censor(self, text: str, return_bool=False) -> Union[str, bool]:
        """:return: text with any profane words censored or bool (True - text has profane words, False otherwise) if
        return_bool=True"""
        result = ''
        text_parts = self._split_by_language(text=text)
        for language, text_part in text_parts:
            result_part = text_part
            doc = self._parse(language=language, text=text_part)
            for token in doc:
                if token._.is_profane:
                    if return_bool:
                        return True
                    else:
                        result_part = self._replace_token(text=result_part, old=token, new=token._.censored)
            result += result_part
        if return_bool:
            return False
        else:
            return result
