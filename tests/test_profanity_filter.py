from collections import defaultdict

import pytest
from ordered_set import OrderedSet

from profanity_filter import ProfanityFilter, MULTILINGUAL_AVAILABLE, Word
from profanity_filter.profanity_filter import ProfaneWordDictionaries


TEST_STATEMENT = "Hey, I like unicorns, chocolate, oranges and man's blood, Turd!"
CLEAN_STATEMENT = "Hey there, I like chocolate too mate."


def create_profane_word_dictionaries(**kwargs) -> ProfaneWordDictionaries:
    return defaultdict(lambda: OrderedSet(), **kwargs)


@pytest.fixture
def profanity_filter():
    return ProfanityFilter()


@pytest.fixture
def custom_profane_word_dictionaries():
    return create_profane_word_dictionaries()


@pytest.fixture
def extra_profane_word_dictionaries():
    return create_profane_word_dictionaries(en=OrderedSet())


@pytest.fixture
def profanity_filter_ru_en():
    return ProfanityFilter(languages=['ru', 'en'])


@pytest.fixture(autouse=True)
def skip_if_deep_analysis_is_disabled(request, profanity_filter):
    if request.node.get_marker('skip_if_deep_analysis_is_disabled'):
        if not profanity_filter.deep_analysis:
            pytest.skip("Couldn't initialize deep analysis")


@pytest.fixture(autouse=True)
def skip_if_deep_analysis_is_disabled_ru_en(request, profanity_filter_ru_en):
    if request.node.get_marker('skip_if_deep_analysis_is_disabled'):
        if not profanity_filter_ru_en.deep_analysis:
            pytest.skip("Couldn't initialize deep analysis")


@pytest.fixture(autouse=True)
def skip_if_polyglot_is_not_available(request):
    if request.node.get_marker('skip_if_polyglot_is_not_available'):
        if not MULTILINGUAL_AVAILABLE:
            pytest.skip("Couldn't initialize polyglot for language detection")


def test_censor_word(profanity_filter):
    world_word = profanity_filter.censor_word('world')
    assert world_word == Word(uncensored='world', censored='world')
    assert not world_word.is_profane
    shiiit_word = profanity_filter.censor_word('shiiit')
    assert shiiit_word == Word(uncensored='shiiit', censored='******', original_profane_word='shit')
    assert shiiit_word.is_profane


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
    assert 'Turd' in censored


def test_extra_profane_word_dictionaries(profanity_filter, extra_profane_word_dictionaries):
    assert extra_profane_word_dictionaries == profanity_filter.extra_profane_word_dictionaries
    profanity_filter.extra_profane_word_dictionaries = {'en': ['hey', 'like']}
    assert (profanity_filter.extra_profane_word_dictionaries ==
            create_profane_word_dictionaries(en=OrderedSet(['hey', 'like'])))
    censored = profanity_filter.censor(TEST_STATEMENT)
    assert 'oranges' in censored
    assert 'Hey' not in censored
    assert 'like' not in censored
    assert 'Turd' not in censored


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
    profanity_filter.custom_profane_word_dictionaries = {'en': ['man']}
    assert profanity_filter.censor(TEST_STATEMENT) == "Hey, I like unicorns, chocolate, oranges and ***'s blood, Turd!"


def test_lemmatization(profanity_filter):
    assert profanity_filter.is_profane('Dick')
    assert profanity_filter.is_profane('DICK')
    assert profanity_filter.is_profane('dIcK')
    assert profanity_filter.is_profane('dicks')
    assert profanity_filter.is_profane('fucks')


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_deep_analysis(profanity_filter):
    assert profanity_filter.censor('duck') == 'duck'
    assert profanity_filter.censor('sh1t') == '****'
    assert profanity_filter.censor('mulkku0') == '*******'
    assert profanity_filter.censor('oofucko') == '*******'
    assert profanity_filter.censor('fuckfuck') == '********'
    assert profanity_filter.censor('addflxppxpfs') == 'addflxppxpfs'
    assert profanity_filter.censor('.s.h.i.t.') == '********.'
    assert profanity_filter.censor('*s*h*i*t*') == '*********'
    assert profanity_filter.censor('sh!t') == '****'


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_deep_analysis_with_censor_whole_words_false(profanity_filter):
    profanity_filter.censor_whole_words = False
    assert not profanity_filter.censor_whole_words
    assert profanity_filter.censor('mulkku0') == '******0'
    assert profanity_filter.censor('oofucko') == 'oo****o'
    assert profanity_filter.censor('h0r1h0r1') == '***1***1'


def test_without_deep_analysis(profanity_filter):
    profanity_filter.deep_analysis = False
    assert profanity_filter.censor('mulkku0') == 'mulkku0'
    assert profanity_filter.censor('oofuckoo') == 'oofuckoo'
    assert profanity_filter.censor('fuckfuck') == 'fuckfuck'


def test_russian(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor('бля') == '***'


@pytest.mark.skip_if_deep_analysis_is_disabled
def test_russian_deep_analysis(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor('забляканный') == '***********'


@pytest.mark.skip_if_polyglot_is_not_available
def test_multilingual(profanity_filter_ru_en):
    assert profanity_filter_ru_en.censor("Да бля, это просто shit какой-то!") == "Да ***, это просто **** какой-то!"
