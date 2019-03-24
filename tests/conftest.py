from collections import defaultdict

import pytest
from ordered_set import OrderedSet

from profanity_filter.profanity_filter import ProfanityFilter, MULTILINGUAL_ANALYSIS_AVAILABLE
from profanity_filter.types_ import ProfaneWordDictionaries


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
def skip_if_multilingual_analysis_is_not_available(request):
    if request.node.get_marker('skip_if_multilingual_analysis_is_not_available'):
        if not MULTILINGUAL_ANALYSIS_AVAILABLE:
            pytest.skip("Couldn't initialize multilingual analysis")


TEST_STATEMENT = "Hey, I like unicorns, chocolate, oranges and man's blood, turd!"
CLEAN_STATEMENT = "Hey there, I like chocolate too mate."
