from typing import List, Optional

from pathlib import Path
from pydantic import BaseModel
from ruamel.yaml import YAML

from profanity_filter.types_ import AnalysisType, Language, PathOrStr


_yaml = YAML(typ='safe')


# noinspection PyTypeChecker
class Config(BaseModel):
    analyses: List[AnalysisType] = list(AnalysisType)
    cache_redis_connection_url: Optional[str] = None
    censor_char: str = '*'
    censor_whole_words: bool = True
    languages: List[Language] = ['en']
    max_relative_distance: float = 0.34

    @classmethod
    def from_yaml(cls, path: PathOrStr) -> 'Config':
        config_dict = _yaml.load(open(str(path)))
        if config_dict is None:
            config_dict = {}
        if 'analyses' in config_dict:
            config_dict['analyses'] = [AnalysisType(analysis) for analysis in config_dict['analyses']]
        return cls(**config_dict)

    def to_yaml(self, path: PathOrStr, exist_ok: bool = True) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not exist_ok and path.exists():
            raise FileExistsError(f"File exists: '{path}'")
        config_dict = self.dict(exclude=set('analyses'))
        config_dict['analyses'] = [analysis.value for analysis in self.analyses]
        with open(str(path), 'w') as f:
            _yaml.dump(config_dict, f)


DEFAULT_CONFIG = Config()
