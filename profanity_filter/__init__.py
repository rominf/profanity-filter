from profanity_filter.console import main
from profanity_filter.profanity_filter import (DEEP_ANALYSIS_AVAILABLE, MORPHOLOGICAL_ANALYSIS_AVAILABLE,
                                               MULTILINGUAL_ANALYSIS_AVAILABLE, ProfanityFilter, __version__,
                                               default_config)
from profanity_filter.spacy_component import SpacyProfanityFilterComponent
from profanity_filter.types_ import ProfanityFilterError, Word, Config
