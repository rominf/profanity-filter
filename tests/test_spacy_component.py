from itertools import chain

from profanity_filter import Config
from tests.conftest import TEST_STATEMENT, with_config


@with_config(Config(analyses=frozenset()))
def test_spacy_component(nlp):
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
