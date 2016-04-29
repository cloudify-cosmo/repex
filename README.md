repex (REPlace (regular) EXpression)
====================================

[![Circle CI](https://circleci.com/gh/cloudify-cosmo/repex/tree/master.svg?style=shield)](https://circleci.com/gh/cloudify-cosmo/repex/tree/master)
[![Build Status](https://travis-ci.org/cloudify-cosmo/repex.svg?branch=master)](https://travis-ci.org/cloudify-cosmo/repex)
[![Build status](https://ci.appveyor.com/api/projects/status/kn6yqwqhsdn54ich/branch/master?svg=true)](https://ci.appveyor.com/project/Cloudify/repex/branch/master)
[![PyPI](http://img.shields.io/pypi/dm/repex.svg)](http://img.shields.io/pypi/dm/repex.svg)
[![PypI](http://img.shields.io/pypi/v/repex.svg)](http://img.shields.io/pypi/v/repex.svg)

NOTE: Beginning with `repex 0.4.1`, file attributes are kept when replacing.

NOTE: Beginning with `repex 0.4.3`, Windows is officially supported (and tested via appveyor).


`repex` replaces strings in single/multiple files based on regular expressions.

Why not use sed you ask? Because `repex` provides some layers of protection and an easy to use config yaml in which you easily add new files and folders to iterate through.

The layers are:
* Match and only then replace in the matched regular expression which allows the user to provide context for the replacement instead of just iterating through the entire file.
* Check for existing strings in a file before replacing anything.
* Exclude files and folders so that you don't screw up.
* Validate that the replacement went as expected by allowing to execute a validation function post-replacement.

AND, you can use variables (sorta jinja2 style). How cool is that? See reference config below.


## Installation

```shell
pip install repex
```

For dev:

```shell
pip install https://github.com/cloudify-cosmo/repex/archive/master.tar.gz
```

## Usage

### CLI

Repex exposes a CLI which can be used to do one of two things:

1. Use repex's power to basically replace sed in the command line.
2. Execute repex using a config file.

#### Using repex like sed

Just like sed:

```bash
rpx repl --path /path/to/my/file --replace 3.3 --rwith 3.4
```

Much, much more than sed:

```bash
rpx repl -p check_validity/resources/\* -t VERSION -r 3.3.0-m\\d+ -w 2.1.1 --validator check_validity/resources/validator.py:validate --must-include blah --must-include yay! --exclude check_validity/resources/VERSION --exclude another/VERSION --validate-before -v
```

This will look for all files named "VERISON" under all folders named "check_validity/resources/*"; replace all strings matching "3.3.0-m\d+" with "2.1.1"; validate using the "validate" function found in "check_validity/resources/validator.py" only if the files found include the strings "blah" and "yay!" excluding specifically the files "check_validity/resources/VERSION" and "another/VERSION".

Note that you must escape special chars where applicable, that is, where regex strings are provided and bash expansion takes place.

#### Notes

* In complex scenarios, while the CLI can execute repex, it will be more likely that you would use the Python API to execute the `iterate` function as you will most probably want to dynamically pass variables according to certain logic provided by your system.
* Variables provided via the `--var` flag will override variables provided within the `--vars-file`.
* Currently, you can't pass variables which contain a `=` within them.

#### Passing a config file to the CLI

Passing a config file to the CLI is done as follows:

```bash
rpx iter -c config.yaml -t my_tag -v --vars-file vars.yaml --var 'x'='y' --var 'version'='3.3.0-m3'
```

See below for how to use the config file.


### Config file based usage 

Using a config file adds some cool features and allows to run repex on multiple paths using a single config file.

Let's say you have files named "VERSION" in different directories which look like this:

```json
{
  "date": "",
  "commit": "",
  "version": "3.3.0-m2",
  "version_other": "3.1.2-m1",
  "build": "8"
}
```

And you'd like to replace 3.3.0-m2 with 3.3.0-m3 in all of those files

You would create a repex config.yaml with the following:

```yaml

variables:
    base_dir: .
    valstr: 'date'
    regex: '\d+(\.\d+){1,2}(-(m|rc)(\d+)?)?'

paths:
    -   type: VERSION
        path: resources
        tags:
            - my_tag
            - my_other_tag
        excluded:
            - x/y/VERSION
        base_directory: "{{ .base_dir }}"
        match: '"version": "{{ .regex }}'
        replace: "{{ .regex }}"
        with: "{{ .version }}"
        validate_before: true
        must_include:
            - "{{ .valstr }}"
            - commit
            - version
        validator:
            type: per_file
            path: '{{ .basedir }}/validator/script/path.py'
            function: my_validation_function
```

and do the following

```python

import os
import repex.repex as rpx

CONFIG_YAML_FILE = "config.yaml"
VERSION = os.environ['VERSION']  # '3.1.0-m3'

variables = {
    'version': VERSION,
}

rpx.iterate(CONFIG_YAML_FILE, variables)

```

and even add a validator file:

```python

def my_validation_function(version_file_path, logger):
    logger.debug('Validating my thing...')
    result = verify_replacement()
    return result == 'yay! it passed!'

```

## Config YAML Explained

IMPORTANT NOTE: variables MUST be enclosed within single or double quotes or they will not expand! Might fix that in future versions...

ANOTHER IMPORTANT NOTE: variables must be structured EXACTLY like this: {{ .VER_NAME }}
Don't forget the spaces!

- `variables` is a dict of variables you can use throughout the config. See below for more info.
- `type` is a regex string representing the file name you're looking for.
- `path` is a regex string representing the path in which you'd like to search for files (so, for instance, if you only want to replace files in directory names starting with "my-", you would write "my-.*"). If `path` is a path to a single file, the `type` attribute must not be configured.
- `tags` is a list of tags to apply to the path. Tags are used for Repex's triggering mechanism to allow you to choose which paths you want to address in every single execution. More on that below.
- `excluded` is a list of excluded paths. The paths must be relative to the working directory, NOT to the `path` variable.
- `base_directory` is the directory from which you'd like to start the recursive search for files. If `path` is a path to a file, this property can be omitted. Alternatively, you can set the `base_directory` and a `path` relative to it.
- `match` is the initial regex based string you'd like to match before replacing the expression. This provides a more robust way of replacing strings where you first match the exact area in which you'd like to replace the expression and only then match the expression you want to replace within it. It also provides a way to replace only specific instances of an expression, and not all.
- `replace` - which regex would you like to replace?
- `with` - what you replace with.
- `validate_before` - a flag stating that you'd like to validate that the pattern you're looking for exists in the file and that all strings in `must_include` exists in the file as well.
- `must_include` - as an additional layer of security, you can specify a set of regex based strings to look for to make sure that the files you're dealing with are the actual files you'd like to replace the expressions in.
- `validator` - validator allows you to run a validation function after replacing expressions. It receives `type` which can be either `per_file` or `per_type` where `per_file` runs the validation on every file while `per_type` runs once for every `type` of file; it receives a `path` to the script and a `function` within the script to call. Note that each validation function must return `True` if successful while any other return value will fail the validation. The validating function receives the file's path as and a logger as parameters.

In case you're providing a path to a file rather than a directory:

- `type` and `base_directory` are depracated
- you can provide a `to_file` key with the path to the file you'd like to create after replacing.


## Tags

Tags allow a user to choose a set of paths on each execution.
A user could apply a list of tags to a path and then, executing repex will address these paths according to the following logic:

* If a user supplied a list of tags and the path was applied a list of tags, the path will be addressed only if matching tags were found.
* If a user supplied a list of tags and the path contains no tags, the path will be ignored.
* If a user did not supply tags and the path contains tags, the path will be ignored.
* If a user did not supply tags and the path does not contain tags, the path will be addressed.
* If a user proivded `any` as a tag, all paths, regardless of whether they have or haven't tags will be addressed.

## Variables

Variables are one of the strongest features of repex. They provide a way of injecting dynamic info to the config file.

Variables can be declared in 4 ways:
- Provided via the CLI
- Provided via the API.
- Harcoded in the config under a top level `variables` section.
- Set as Environment Variables.

See the example above for a variable definition reference.

Some important facts about variables:

- Variables with the same name sent via the API will override the hardcoded ones.
- API provided or hardcoded variables can be overriden if env vars exist with the same name but in upper case and prefixed with `REPEX_VAR_` (so the variable "version" can be overriden by an env var called "REPEX_VAR_VERSION".) This can help with, for example, using the $BUILD_NUMBER env var in Jenkins to update a file with the new build number.

## Testing

NOTE: Running the tests require an internet connection

```shell
git clone git@github.com:cloudify-cosmo/repex.git
cd repex
pip install tox
tox
```

## Contributions..

Pull requests are always welcome..
