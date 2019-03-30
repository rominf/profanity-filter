from collections import defaultdict

import pytest
import spacy.language
from ordered_set import OrderedSet

from profanity_filter.profanity_filter import ProfanityFilter
from profanity_filter.types_ import Config, ProfaneWordDictionaries


def create_profane_word_dictionaries(**kwargs) -> ProfaneWordDictionaries:
    return defaultdict(lambda: OrderedSet(), **kwargs)


@pytest.fixture
def empty_profane_word_dictionaries() -> ProfaneWordDictionaries:
    return create_profane_word_dictionaries()


@pytest.fixture
def pf(request) -> ProfanityFilter:
    config: Config = request.param
    result = ProfanityFilter(
        languages=config.languages,
        analyses=config.analyses,
        censor_char=config.censor_char,
        censor_whole_words=config.censor_whole_words,
        max_relative_distance=config.max_relative_distance,
    )
    for analysis in config.analyses:
        if analysis not in result.analyses:
            pytest.skip(f"Couldn't initialize {analysis.value} analysis")
    return result


@pytest.fixture
def nlp(pf) -> spacy.language.Language:
    nlp = spacy.load('en')
    nlp.add_pipe(pf.spacy_component, last=True)
    return nlp


def with_config(config: Config):
    def decorator(f):
        return pytest.mark.parametrize('pf', [config], indirect=True, ids=[''])(f)

    return decorator


TEST_STATEMENT = "Hey, I like unicorns, chocolate, oranges and man's blood, turd!"
CLEAN_STATEMENT = "Hey there, I like chocolate too mate."
