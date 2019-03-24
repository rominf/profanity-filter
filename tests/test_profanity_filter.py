from itertools import chain

import spacy

import pytest
from ordered_set import OrderedSet

from profanity_filter.types_ import Word
from tests.conftest import create_profane_word_dictionaries, TEST_STATEMENT, CLEAN_STATEMENT


def test_censor_word(profanity_filter):
    world_word = profanity_filter.censor_word('world')
    assert world_word == Word(uncensored='world', censored='world')
    assert not world_word.is_profane
    shiiit_word = profanity_filter.censor_word('shiiit')
    assert shiiit_word == Word(uncensored='shiiit', censored='******', original_profane_word='shit')
    assert shiiit_word.is_profane
    fuk_word = profanity_filter.censor_word('FUK')
    assert fuk_word == Word(uncensored='FUK', censored='***', original_profane_word='fuk')


def test_is_profane(profanity_filter):
    assert profanity_filter.is_profane(TEST_STATEMENT)
    assert not profanity_filter.is_profane(CLEAN_STATEMENT)


def test_is_clean(profanity_filter):
    assert not profanity_filter.is_clean(TEST_STATEMENT)
    assert profanity_filter.is_clean(CLEAN_STATEMENT)


def test_censor_char(profanity_filter):
    assert profanity_filter.censor_char == '*'
    assert profanity_filter.censor(TEST_STATEMENT) == "Hey, I like unicorns, chocolate, oranges and man's blood, ****!"
    profanity_filter.censor_char = '#'
    assert profanity_filter.censor_char == '#'
    assert profanity_filter.censor(TEST_STATEMENT) == "Hey, I like unicorns, chocolate, oranges and man's blood, ####!"


def test_custom_profane_word_dictionaries(profanity_filter, custom_profane_word_dictionaries):
    assert custom_profane_word_dictionaries == custom_profane_word_dictionaries
    # Testing pluralization here as well
    profanity_filter.custom_profane_word_dictionaries = {'en': ['unicorn', 'chocolate']}
    assert (profanity_filter.custom_profane_word_dictionaries ==
            create_profane_word_dictionaries(en=OrderedSet(['unicorn', 'chocolate'])))
    censored = profanity_filter.censor(TEST_STATEMENT)
    assert 'unicorns' not in censored
    assert 'chocolate' not in censored
    assert 'turd' in censored


def test_extra_profane_word_dictionaries(profanity_filter, extra_profane_word_dictionaries):
    assert extra_profane_word_dictionaries == profanity_filter.extra_profane_word_dictionaries
    profanity_filter.extra_profane_word_dictionaries = {'en': ['hey', 'like']}
    assert (profanity_filter.extra_profane_word_dictionaries ==
            create_profane_word_dictionaries(en=OrderedSet(['hey', 'like'])))
    censored = profanity_filter.censor(TEST_STATEMENT)
    assert 'oranges' in censored
    assert 'Hey' not in censored
    assert 'like' not in censored
    assert 'turd' not in censored


def test_restore_words(profanity_filter, custom_profane_word_dictionaries, extra_profane_word_dictionaries):
    profanity_filter.custom_profane_word_dictionaries = {'en': ['cupcakes']}
    profanity_filter.extra_profane_word_dictionaries = {'en': ['dibs']}
    profanity_filter.restore_profane_word_dictionaries()
    assert profanity_filter.custom_profane_word_dictionaries == custom_profane_word_dictionaries
    assert profanity_filter.extra_profane_word_dictionaries == extra_profane_word_dictionaries
    profane_word_dictionaries = profanity_filter.profane_word_dictionaries
    assert 'dibs' not in profane_word_dictionaries['en']
    assert 'cupcakes' not in profane_word_dictionaries['en']


def test_tokenization(profanity_filter):
    profanity_filter.custom_profane_word_dictionaries = {'en': ['chocolate']}
    assert profanity_filter.censor(TEST_STATEMENT) == "Hey, I like unicorns, *********, oranges and man's blood, turd!"


def test_without_deep_analysis(profanity_filter):
    profanity_filter.deep_analysis = False
    assert profanity_filter.censor('mulkku0') == 'mulkku0'
    assert profanity_filter.censor('oofuckoo') == 'oofuckoo'
    assert profanity_filter.censor('fuckfuck') == 'fuckfuck'


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_deep_analysis(profanity_filter):
    assert profanity_filter.censor('duck') == 'duck'
    assert profanity_filter.censor('sh1t') == '****'
    assert profanity_filter.censor('sh5t') == '****'
    assert profanity_filter.censor('mulkku0') == '*******'
    assert profanity_filter.censor('oofucko') == '*******'
    assert profanity_filter.censor('fuckfuck') == '********'
    assert profanity_filter.censor('addflxppxpfs') == 'addflxppxpfs'
    assert profanity_filter.censor('.s.h.i.t.') == '********.'
    assert profanity_filter.censor('*s*h*i*t*') == '*********'
    assert profanity_filter.censor('sh!t') == '****'


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_deep_analysis_lemmatization(profanity_filter):
    assert profanity_filter.is_profane('FUK')
    assert profanity_filter.is_profane('Dick')
    assert profanity_filter.is_profane('DICK')
    assert profanity_filter.is_profane('dIcK')
    assert profanity_filter.is_profane('dicks')
    assert profanity_filter.is_profane('fucks')


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_deep_analysis_with_censor_whole_words_false(profanity_filter):
    profanity_filter.censor_whole_words = False
    assert not profanity_filter.censor_whole_words
    assert profanity_filter.censor('mulkku0') == '******0'
    assert profanity_filter.censor('oofucko') == 'oo****o'
    assert profanity_filter.censor('h0r1h0r1') == '***1***1'


def test_russian(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor('бля') == '***'


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_russian_deep_analysis(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor('забляканный') == '***********'


@pytest.mark.skip_if_multilingual_analysis_is_not_available
def test_multilingual(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor("Да бля, это просто shit какой-то!") == "Да ***, это просто **** какой-то!"


def test_spacy_component(profanity_filter):
    nlp = spacy.load('en')
    nlp.add_pipe(profanity_filter.spacy_component, last=True)
    doc = nlp(TEST_STATEMENT)

    assert doc._.is_profane

    assert not doc[:-2]._.is_profane and not doc[-1:]._.is_profane
    assert doc[-2:-1]._.is_profane

    for token in chain(doc[:-2], doc[-1:]):
        assert token._.censored == token.text
        assert not token._.is_profane
        assert token._.original_profane_word is None
    assert doc[-2]._.censored == '****'
    assert doc[-2]._.is_profane
    assert doc[-2]._.original_profane_word == 'turd'
