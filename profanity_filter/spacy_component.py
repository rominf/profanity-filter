from contextlib import suppress
from typing import Union, Optional, Generator, List

import spacy.language
from more_itertools import partitions
from spacy.tokens import Doc, Span, Token

from profanity_filter import spacy_utlis
from profanity_filter.types_ import Language


class SpacyProfanityFilterComponent:
    name = 'profanity_filter'

    # noinspection PyUnresolvedReferences
    def __init__(self, profanity_filter: 'ProfanityFilter', nlp: spacy.language.Language, language: Language = None,
                 stop_on_first_profane_word: bool = False):
        self._language = language
        self._nlp = nlp  # Used only for tokenization
        self._profanity_filter = profanity_filter
        self._stop_on_first_profane_word = stop_on_first_profane_word

    # noinspection PyProtectedMember
    def __call__(self, doc: Doc, language: Language = None, stop_on_first_profane_word: Optional[bool] = None) -> Doc:
        self.register_extensions(exist_ok=True)
        if language is None:
            language = self._language
        if stop_on_first_profane_word is None:
            stop_on_first_profane_word = self._stop_on_first_profane_word
        i = 0
        while i < len(doc):
            j = i + 1
            while (j < len(doc)
                   and not doc[j - 1].whitespace_ and not doc[j - 1].is_space and not doc[j - 1].is_punct
                   and not doc[j].is_space and not doc[j].is_punct):
                j += 1
            span = self._censor_spaceless_span(doc[i:j], language=language)
            if stop_on_first_profane_word and span._.is_profane:
                break
            i += len(span)
        return doc

    @staticmethod
    def register_extensions(exist_ok: bool = False) -> None:
        def do() -> None:
            Token.set_extension('censored', default=None)
            Token.set_extension('is_profane', getter=SpacyProfanityFilterComponent.token_is_profane)
            Token.set_extension('original_profane_word', default=None)

            Span.set_extension('is_profane', getter=SpacyProfanityFilterComponent.tokens_are_profane)
            Doc.set_extension('is_profane', getter=SpacyProfanityFilterComponent.tokens_are_profane)

        if exist_ok:
            with suppress(ValueError):
                do()
        else:
            do()

    @staticmethod
    def token_is_profane(token: Token) -> bool:
        # noinspection PyProtectedMember
        return token._.censored != token.text

    @staticmethod
    def tokens_are_profane(tokens: Union[Doc, Span]) -> bool:
        # noinspection PyProtectedMember
        return any(token._.is_profane for token in tokens)

    def _span_partitions(self, span: Span) -> Generator[List[Token], None, None]:
        if len(span) == 1:
            return span[0]
        for partition in partitions(span):
            yield [spacy_utlis.make_token(nlp=self._nlp, word=''.join(element)) for element in partition]

    # noinspection PyProtectedMember
    def _censor_spaceless_span(self, span: Span, language: Language) -> Span:
        token = spacy_utlis.make_token(nlp=self._nlp, word=str(span) if len(span) > 1 else span[0])
        censored_word = self._profanity_filter.censor_word(word=token, language=language)
        if censored_word.is_profane:
            with span.doc.retokenize() as retokenizer:
                retokenizer.merge(span)
            token = span[0]
            token._.censored = censored_word.censored
            token._.original_profane_word = censored_word.original_profane_word
        else:
            for token in span:
                token._.censored = token.text
        return span
