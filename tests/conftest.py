from collections import defaultdict

import pytest
import spacy.language
from ordered_set import OrderedSet

from profanity_filter.profanity_filter import ProfanityFilter, MULTILINGUAL_ANALYSIS_AVAILABLE
from profanity_filter.types_ import ProfaneWordDictionaries


def create_profane_word_dictionaries(**kwargs) -> ProfaneWordDictionaries:
    return defaultdict(lambda: OrderedSet(), **kwargs)


@pytest.fixture
def empty_profane_word_dictionaries() -> ProfaneWordDictionaries:
    return create_profane_word_dictionaries()


@pytest.fixture
def pf() -> ProfanityFilter:
    return ProfanityFilter()


@pytest.fixture
def pf_with_deep_analysis_false(pf) -> ProfanityFilter:
    pf.deep_analysis = False
    return pf


@pytest.fixture
def pf_with_censor_whole_words_false(pf) -> ProfanityFilter:
    pf.censor_whole_words = False
    return pf


@pytest.fixture
def pf_ru_en() -> ProfanityFilter:
    return ProfanityFilter(languages=['ru', 'en'])


@pytest.fixture
def nlp() -> spacy.language.Language:
    nlp = spacy.load('en')
    pf = ProfanityFilter(nlps={'en': nlp})
    nlp.add_pipe(pf.spacy_component, last=True)
    return nlp


@pytest.fixture(autouse=True)
def skip_if_deep_analysis_is_disabled(request, pf):
    if request.node.get_marker('skip_if_deep_analysis_is_disabled'):
        if not pf.deep_analysis:
            pytest.skip("Couldn't initialize deep analysis")


@pytest.fixture(autouse=True)
def skip_if_deep_analysis_is_disabled_ru_en(request, pf_ru_en):
    if request.node.get_marker('skip_if_deep_analysis_is_disabled'):
        if not pf_ru_en.deep_analysis:
            pytest.skip("Couldn't initialize deep analysis")


@pytest.fixture(autouse=True)
def skip_if_multilingual_analysis_is_not_available(request):
    if request.node.get_marker('skip_if_multilingual_analysis_is_not_available'):
        if not MULTILINGUAL_ANALYSIS_AVAILABLE:
            pytest.skip("Couldn't initialize multilingual analysis")


TEST_STATEMENT = "Hey, I like unicorns, chocolate, oranges and man's blood, turd!"
CLEAN_STATEMENT = "Hey there, I like chocolate too mate."
