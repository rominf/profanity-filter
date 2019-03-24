from typing import Union

import spacy.language
from spacy.tokens import Doc, Token

from profanity_filter.spacy_component import SpacyProfanityFilterComponent
from profanity_filter.types_ import Language


def parse(nlp: spacy.language.Language,
          text: str, language: Language = None,
          use_profanity_filter: bool = False) -> Union[Doc, Token]:
    disable = [] if use_profanity_filter else [SpacyProfanityFilterComponent.name]
    component_cfg = {}
    if use_profanity_filter:
        component_cfg[SpacyProfanityFilterComponent.name] = {
            'language': language,
        }
    return nlp(text, disable=disable, component_cfg=component_cfg)


def make_token(nlp: spacy.language.Language, word: Union[str, Token]) -> Token:
    if hasattr(word, 'text'):
        return word
    doc = parse(nlp=nlp, text=word)
    with doc.retokenize() as retokenizer:
        retokenizer.merge(doc[:])
    return doc[0]
