"""RESTful web service for profanity filtering"""

from contextlib import suppress

import pathlib
from appdirs import AppDirs
from fastapi import FastAPI, Path

from profanity_filter.config import DEFAULT_CONFIG
from profanity_filter.profanity_filter import ProfanityFilter, APP_NAME


def create_profanity_filter() -> ProfanityFilter:
    app_dirs = AppDirs(APP_NAME)
    config_path = pathlib.Path(app_dirs.user_config_dir) / 'web-config.yaml'
    with suppress(FileExistsError):
        DEFAULT_CONFIG.to_yaml(config_path, exist_ok=False)
    return ProfanityFilter.from_yaml(config_path)


app = FastAPI()
pf = create_profanity_filter()


@app.post(path='/censor-word/{word}')
async def censor_word(word: str = Path(..., title='Word to censor', description='Word to censor')):
    return pf.censor_word(word)
