import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from ordered_set import OrderedSet
from ruamel.yaml import YAML

from profanity_filter.profanity_filter import ProfanityFilter, DEFAULT_CONFIG
from profanity_filter.types_ import Word, AnalysisType
from profanity_filter.config import Config

from tests.conftest import (create_profane_word_dictionaries, TEST_STATEMENT, CLEAN_STATEMENT, with_config,
                            Config as TestConfig)


def compare_settings(pf0: ProfanityFilter, pf1: ProfanityFilter) -> None:
    assert pf0.analyses == pf1.analyses
    assert pf0.cache_redis_connection_url == pf1.cache_redis_connection_url
    assert pf0.censor_char == pf1.censor_char
    assert pf0.custom_profane_word_dictionaries == pf1.custom_profane_word_dictionaries
    assert pf0.extra_profane_word_dictionaries == pf1.extra_profane_word_dictionaries
    assert pf0.languages == pf1.languages
    assert pf0.max_relative_distance == pf1.max_relative_distance


def test_from_config():
    compare_settings(ProfanityFilter(), ProfanityFilter.from_config(DEFAULT_CONFIG))


def test_from_yaml():
    non_existing_path = uuid.uuid4().hex
    with pytest.raises(FileNotFoundError):
        ProfanityFilter.from_yaml(non_existing_path)

    with NamedTemporaryFile() as f:
        compare_settings(ProfanityFilter(), ProfanityFilter.from_yaml(f.name))

    with NamedTemporaryFile() as f:
        config = Config(
            analyses=[AnalysisType.DEEP, AnalysisType.MULTILINGUAL],
            censor_char='#',
            censor_whole_words=False,
            languages=['ru', 'en'],
            max_relative_distance=0.2,
        )
        config_dict = config.dict()
        config_dict['analyses'] = [analysis.value for analysis in config_dict['analyses']]
        yaml = YAML(typ='safe')
        yaml.dump(data=config_dict, stream=Path(f.name))
        compare_settings(ProfanityFilter.from_config(config), ProfanityFilter.from_yaml(f.name))


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP])))
def test_censor_word(pf):
    world_word = pf.censor_word('world')
    assert world_word == Word(uncensored='world', censored='world')
    assert not world_word.is_profane
    shiiit_word = pf.censor_word('shiiit')
    assert shiiit_word == Word(uncensored='shiiit', censored='******', original_profane_word='shit')
    assert shiiit_word.is_profane


@with_config(TestConfig())
def test_is_profane(pf):
    assert pf.is_profane(TEST_STATEMENT)
    assert not pf.is_profane(CLEAN_STATEMENT)


@with_config(TestConfig())
def test_is_clean(pf):
    assert not pf.is_clean(TEST_STATEMENT)
    assert pf.is_clean(CLEAN_STATEMENT)


@with_config(TestConfig())
def test_censor_char(pf):
    assert pf.censor_char == '*'
    assert pf.censor_word('fuck') == Word(uncensored='fuck', censored='****', original_profane_word='fuck')
    pf.censor_char = '#'
    assert pf.censor_char == '#'
    assert pf.censor_word('fuck') == Word(uncensored='fuck', censored='####', original_profane_word='fuck')


@with_config(TestConfig())
def test_custom_profane_word_dictionaries(pf, empty_profane_word_dictionaries):
    assert pf.custom_profane_word_dictionaries == empty_profane_word_dictionaries
    profane_words = ['unicorn', 'windows']
    pf.custom_profane_word_dictionaries = {'en': profane_words}
    assert (pf.custom_profane_word_dictionaries == create_profane_word_dictionaries(en=OrderedSet(profane_words)))
    assert pf.censor_word('unicorn') == Word(uncensored='unicorn', censored='*******', original_profane_word='unicorn')
    assert pf.censor_word('windows') == Word(uncensored='windows', censored='*******', original_profane_word='windows')
    assert pf.censor_word('fuck') == Word(uncensored='fuck', censored='fuck', original_profane_word=None)


@with_config(TestConfig())
def test_extra_profane_word_dictionaries(pf, empty_profane_word_dictionaries):
    assert pf.extra_profane_word_dictionaries == empty_profane_word_dictionaries
    extra_profane_words = ['hey', 'like']
    pf.extra_profane_word_dictionaries = {'en': extra_profane_words}
    assert (pf.extra_profane_word_dictionaries == create_profane_word_dictionaries(en=OrderedSet(extra_profane_words)))
    assert pf.censor_word('hey') == Word(uncensored='hey', censored='***', original_profane_word='hey')
    assert pf.censor_word('like') == Word(uncensored='like', censored='****', original_profane_word='like')
    assert pf.censor_word('fuck') == Word(uncensored='fuck', censored='****', original_profane_word='fuck')


@with_config(TestConfig())
def test_restore_words(pf, empty_profane_word_dictionaries):
    pf.custom_profane_word_dictionaries = {'en': ['cupcakes']}
    pf.extra_profane_word_dictionaries = {'en': ['dibs']}
    pf.restore_profane_word_dictionaries()
    assert pf.custom_profane_word_dictionaries == empty_profane_word_dictionaries
    assert pf.extra_profane_word_dictionaries == empty_profane_word_dictionaries
    profane_word_dictionaries = pf.profane_word_dictionaries
    assert 'dibs' not in profane_word_dictionaries['en']
    assert 'cupcakes' not in profane_word_dictionaries['en']


@with_config(TestConfig())
def test_tokenization(pf):
    pf.custom_profane_word_dictionaries = {'en': ['chocolate']}
    assert pf.censor(TEST_STATEMENT) == "Hey, I like unicorns, *********, oranges and man's blood, turd!"


@with_config(TestConfig())
def test_without_deep_analysis(pf):
    assert pf.censor_word('mulkku0') == Word(uncensored='mulkku0', censored='mulkku0')
    assert pf.censor_word('oofuko') == Word(uncensored='oofuko', censored='oofuko')


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP])))
def test_deep_analysis(pf):
    assert pf.censor_word('duck') == Word(uncensored='duck', censored='duck')
    assert pf.censor_word('addflxppxpfs') == Word(uncensored='addflxppxpfs', censored='addflxppxpfs')
    assert pf.censor_word('mulkku0') == Word(uncensored='mulkku0', censored='*******', original_profane_word='mulkku')
    assert pf.censor_word('oofuko') == Word(uncensored='oofuko', censored='******', original_profane_word='fuck')
    assert pf.censor_word('fuckfuck') == Word(uncensored='fuckfuck', censored='********', original_profane_word='fuck')


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP])))
def test_deep_analysis_tokenization_and_keep_only_letters(nlp):
    doc = nlp('sh1t')
    assert len(doc) == 1
    assert doc[0]._.censored == '****'
    assert doc[0]._.original_profane_word == 'shit'

    doc = nlp('sh!t')
    assert len(doc) == 1
    assert doc[0]._.censored == '****'
    assert doc[0]._.original_profane_word == 'shit'

    doc = nlp('.s.h.i.t.')
    assert len(doc) == 2
    assert doc[0]._.censored == '********'
    assert doc[0]._.original_profane_word == 'shit'
    assert doc[1]._.censored == '.'
    assert doc[1]._.original_profane_word is None

    doc = nlp('*s*h*i*t*')
    assert len(doc) == 3
    assert doc[0]._.censored == '*'
    assert doc[0]._.original_profane_word is None
    assert doc[1]._.censored == '*******'
    assert doc[1]._.original_profane_word == 'shit'
    assert doc[2]._.censored == '*'
    assert doc[2]._.original_profane_word is None


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP])))
def test_deep_analysis_lemmatization(pf):
    assert pf.censor_word('Dick') == Word(uncensored='Dick', censored='****', original_profane_word='dick')
    assert pf.censor_word('DICK') == Word(uncensored='DICK', censored='****', original_profane_word='dick')
    assert pf.censor_word('dIcK') == Word(uncensored='dIcK', censored='****', original_profane_word='dick')
    assert pf.censor_word('dicks') == Word(uncensored='dicks', censored='*****', original_profane_word='dick')
    assert pf.censor_word('fucks') == Word(uncensored='fucks', censored='*****', original_profane_word='fuck')


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP]), censor_whole_words=False))
def test_deep_analysis_with_censor_whole_words_false(pf):
    assert pf.censor_word('mulkku0') == Word(uncensored='mulkku0', censored='******0', original_profane_word='mulkku')
    assert pf.censor_word('oofuko') == Word(uncensored='oofuko', censored='oo***o', original_profane_word='fuck')
    assert pf.censor_word('h0r1h0r1') == Word(uncensored='h0r1h0r1', censored='***1***1', original_profane_word='h0r')


@with_config(TestConfig(languages=('ru', 'en')))
def test_languages(pf):
    assert pf.languages == OrderedSet(['ru', 'en'])
    assert pf.languages_str == 'ru, en'


@with_config(TestConfig(languages=('ru', 'en')))
def test_russian(pf):
    assert pf.censor_word('бля') == Word(uncensored='бля', censored='***', original_profane_word='бля')


@with_config(TestConfig(analyses=frozenset([AnalysisType.DEEP]), languages=('ru', 'en')))
def test_russian_deep_analysis(pf):
    assert pf.censor_word('бл@ка') == Word(uncensored='бл@ка', censored='*****', original_profane_word='бля')


@with_config(TestConfig(analyses=frozenset([AnalysisType.MULTILINGUAL]), languages=('ru', 'en')))
def test_multilingual(pf):
    assert pf.censor("Да бля, это просто shit какой-то!") == "Да ***, это просто **** какой-то!"
