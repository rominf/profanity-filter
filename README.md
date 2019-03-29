# profanity-filter: A Python library for detecting and filtering profanity
[![License](https://img.shields.io/pypi/l/profanity-filter.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/profanity-filter.svg)
[![PyPI](https://img.shields.io/pypi/v/profanity-filter.svg)](https://pypi.org/project/profanity-filter/)

## Table of contents
<!--ts-->
   * [profanity-filter: A Python library for detecting and filtering profanity](#profanity-filter-a-python-library-for-detecting-and-filtering-profanity)
      * [Table of contents](#table-of-contents)
      * [Overview](#overview)
         * [Features](#features)
         * [Caveats](#caveats)
      * [Usage](#usage)
         * [Basics](#basics)
         * [Deep analysis](#deep-analysis)
         * [Multilingual analysis](#multilingual-analysis)
         * [Using as a part of Spacy pipeline](#using-as-a-part-of-spacy-pipeline)
         * [Customizations](#customizations)
         * [Console Executable](#console-executable)
      * [Installation](#installation)
         * [Basic installation](#basic-installation)
         * [Deep analysis](#deep-analysis-1)
         * [Other language support](#other-language-support)
            * [Russian language support](#russian-language-support)
               * [Pymorphy2](#pymorphy2)
         * [Multilingual support](#multilingual-support)
      * [Troubleshooting](#troubleshooting)
      * [Credits](#credits)

<!-- Added by: rominf, at: Пт мар 29 18:06:57 MSK 2019 -->

<!--te-->

## Overview
`profanity-filter` is a universal library for detecting and filtering profanity. Support for English and Russian is 
included.

### Features
1. Full text or individual words censoring.
2. Multilingual support, including profanity filtering in texts written in mixed languages.
3. Deep analysis. The library detects not only the exact profane word matches but also derivative and distorted profane
words using the Levenshtein automata, ignoring dictionary words, containing profane words as a part.
4. Spacy component for using the library as a part of the pipeline.
5. Explanation of decisions (attribute `original_profane_word`).
6. Partial word censoring.
7. Extensibility support. New languages can be added by supplying dictionaries.

### Caveats
1. Context-free. The library cannot detect using profane phrases consisted of decent words. Vice versa, the library
cannot detect appropriate usage of a profane word.

## Usage
Here are the basic examples of how to use the library. For more examples please see `tests` folder.

### Basics
```python
from profanity_filter import ProfanityFilter

pf = ProfanityFilter()

pf.censor("That's bullshit!")
# "That's ********!"

pf.censor_word('fuck')
# Word(uncensored='fuck', censored='****', original_profane_word='fuck')
```

### Deep analysis
```python
from profanity_filter import ProfanityFilter

pf = ProfanityFilter()

pf.censor("fuckfuck")
# "********"

pf.censor_word('oofuko')
# Word(uncensored='oofuko', censored='******', original_profane_word='fuck')

pf.censor_whole_words = False
pf.censor_word('h0r1h0r1')
# Word(uncensored='h0r1h0r1', censored='***1***1', original_profane_word='h0r')
```

### Multilingual analysis
```python
from profanity_filter import ProfanityFilter

pf = ProfanityFilter(languages=['ru', 'en'])

pf.censor("Да бля, это просто shit какой-то!")
# "Да ***, это просто **** какой-то!"
```

### Using as a part of Spacy pipeline
```python
import spacy
from profanity_filter import ProfanityFilter

nlp = spacy.load('en')
profanity_filter = ProfanityFilter(nlps={'en': nlp})  # reuse spacy Language (optional)
nlp.add_pipe(profanity_filter.spacy_component, last=True)

doc = nlp('This is shiiit!')

doc._.is_profane
# True

doc[:2]._.is_profane
# False

for token in doc:
    print(f'{token}: '
          f'censored={token._.censored}, '
          f'is_profane={token._.is_profane}, '
          f'original_profane_word={token._.original_profane_word}'
    )
# This: censored=This, is_profane=False, original_profane_word=None
# is: censored=is, is_profane=False, original_profane_word=None
# shiiit: censored=******, is_profane=True, original_profane_word=shit
# !: censored=!, is_profane=False, original_profane_word=None
```

### Customizations
```python
from profanity_filter import ProfanityFilter

pf = ProfanityFilter()

pf.censor_char = '@'
pf.censor("That's bullshit!")
# "That's @@@@@@@@!"

pf.censor_char = '*'
pf.custom_profane_word_dictionaries = {'en': {'love', 'dog'}}
pf.censor("I love dogs and penguins!")
# "I **** **** and penguins"

pf.restore_profane_word_dictionaries()
pf.is_clean("That's awesome!")
# True

pf.is_clean("That's bullshit!")
# False

pf.is_profane("That's bullshit!")
# True

pf.extra_profane_word_dictionaries = {'en': {'chocolate', 'orange'}}
pf.censor("Fuck orange chocolates")
# "**** ****** **********"
```

### Console Executable
```bash
$ profanity_filter -h
usage: profanity_filter [-h] [-t TEXT | -f PATH] [-l LANGUAGES] [-o OUTPUT_FILE] [--show]

Profanity filter console utility

optional arguments:
  -h, --help            show this help message and exit
  -t TEXT, --text TEXT  Test the given text for profanity
  -f PATH, --file PATH  Test the given file for profanity
  -l LANGUAGES, --languages LANGUAGES
                        Test for profanity using specified languages (comma
                        separated)
  -o OUTPUT_FILE, --output OUTPUT_FILE
                        Write the censored output to a file
  --show                Print the censored text
```

## Installation
First two parts of installation instructions are designed for the users who want to filter English profanity.
If you want to filter profanity in another language you still need to read it.

### Basic installation
For minimal setup you need to install `profanity-filter` with is bundled with `spacy` and download `spacy`
model for tokenization and lemmatization:
```shell
$ pip install profanity-filter
$ # Skip next line if you want to filter profanity in another language
$ python -m spacy download en
```

For more info about Spacy models read: https://spacy.io/usage/models/.

### Deep analysis
To get deep analysis functionality install additional libraries and dictionary for your language.

Firstly, install `hunspell` and `hunspell-devel` packages with your system package manager.

For Amazon Linux AMI run:
```shell
$ sudo yum install hunspell
```

For openSUSE run:
```shell
$ sudo zypper install hunspell hunspell-devel
```

Then run:
```shell
$ pip install -U -r https://raw.githubusercontent.com/rominf/profanity-filter/master/requirements-deep-analysis.txt
$ # Skip next lines if you want deep analysis support for another language (will be covered in next section)
$ cd profanity_filter/data
$ wget https://cgit.freedesktop.org/libreoffice/dictionaries/plain/en/en_US.aff
$ wget https://cgit.freedesktop.org/libreoffice/dictionaries/plain/en/en_US.dic
$ mv en_US.aff en.aff
$ mv en_US.dic en.dic
```

### Other language support
Let's take Russian for example on how to add new language support.

#### Russian language support
Firstly, we need to provide file `profanity_filter/data/ru_badwords.txt` which contains a newline separated list of
profane words. For Russian it's already present, so we skip file generation.

Next, we need to download the appropriate Spacy model. Unfortunately, Spacy model for Russian is not yet ready, so we 
will use an English model for tokenization. If you had not install Spacy model for English, it's the right time to do 
so. As a consequence, even if you want to filter just Russian profanity, you need to specify English in 
`ProfanityFilter` constructor as shown in usage examples.

Next, we download dictionaries in Hunspell format for deep analysis from the site 
https://cgit.freedesktop.org/libreoffice/dictionaries/plain/:
```shell
> cd profanity_filter/data
> wget https://cgit.freedesktop.org/libreoffice/dictionaries/plain/ru_RU/ru_RU.aff
> wget https://cgit.freedesktop.org/libreoffice/dictionaries/plain/ru_RU/ru_RU.dic
> mv ru_RU.aff ru.aff
> mv ru_RU.dic ru.dic
```

##### Pymorphy2
For Russian and Ukrainian languages to achieve better results we suggest you to install `pymorphy2`.
To install `pymorphy2` with Russian dictionary run:
```shell
$ pip install -U -r https://raw.githubusercontent.com/rominf/profanity-filter/master/requirements-pymorphy2-ru.txt
```

### Multilingual support
You need to install `polyglot` package and it's requirements for language detection.
See https://polyglot.readthedocs.io/en/latest/Installation.html for more detailed instructions.

For Amazon Linux AMI run:
```shell
$ sudo yum install libicu-devel
```

For openSUSE run:
```shell
$ sudo zypper install libicu-devel
```

Then run:
```shell
$ pip install -U -r https://raw.githubusercontent.com/rominf/profanity-filter/master/requirements-multilingual.txt
```

## Troubleshooting
You can always check will deep, morphological, and multilingual analyses work by inspecting the value of corresponding
variables. If everything is set up correctly you will see the following:
```python
from profanity_filter import DEEP_ANALYSIS_AVAILABLE, MORPHOLOGICAL_ANALYSIS_AVAILABLE, MULTILINGUAL_ANALYSIS_AVAILABLE

print(DEEP_ANALYSIS_AVAILABLE)
# True

print(MORPHOLOGICAL_ANALYSIS_AVAILABLE)
# True

print(MULTILINGUAL_ANALYSIS_AVAILABLE)
# True
```

If some of variables are not `True`, you can import dependencies yourself to see the import exceptions:
```python
from profanity_filter.analysis.deep import *
from profanity_filter.analysis.morphological import *
from profanity_filter.analysis.multilingual import *
```

## Credits
English profane word dictionary: https://github.com/areebbeigh/profanityfilter/ (author Areeb Beigh).

Russian profane word dictionary: https://github.com/PixxxeL/djantimat (author Ivan Sergeev).
