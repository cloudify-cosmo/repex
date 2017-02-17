repex (REPlace (regular) EXpression)
====================================

[![Build Status](https://travis-ci.org/cloudify-cosmo/repex.svg?branch=master)](https://travis-ci.org/cloudify-cosmo/repex)
[![Build status](https://ci.appveyor.com/api/projects/status/kn6yqwqhsdn54ich/branch/master?svg=true)](https://ci.appveyor.com/project/Cloudify/repex/branch/master)
[![PyPI version](http://img.shields.io/pypi/v/repex.svg)](https://pypi.python.org/pypi/repex)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/repex.svg)](https://img.shields.io/pypi/pyversions/repex.svg)
[![Requirements Status](https://requires.io/github/cloudify-cosmo/repex/requirements.svg?branch=master)](https://requires.io/github/cloudify-cosmo/repex/requirements/?branch=master)
[![Code Coverage](https://codecov.io/github/cloudify-cosmo/repex/coverage.svg?branch=master)](https://codecov.io/github/cloudify-cosmo/repex?branch=master)
[![Code Quality](https://landscape.io/github/cloudify-cosmo/repex/master/landscape.svg?style=flat)](https://landscape.io/github/cloudify-cosmo/repex)
[![Is Wheel](https://img.shields.io/pypi/wheel/repex.svg?style=flat)](https://pypi.python.org/pypi/repex)


NOTE: Beginning with `repex 0.4.1`, file attributes are kept when replacing.

NOTE: Beginning with `repex 0.4.3`, Windows is officially supported (and tested via appveyor).

NOTE: Beggining with `repex 1.0.0`, Python 3 is officially supported.

NOTE: `repex 1.1.0` has breaking CLI and API changes. See [CHANGES](CHANGES) for more information.

NOTE: `repex 1.2.0` does not allow to set variables in the config without providing them.

`repex` replaces strings in single/multiple files based on regular expressions.

Why not Jinja you ask? Because sometimes you have existing files which are not templated in which you'd like to replace things.. and even if they're in your control, sometimes templates are just not viable if you need something working OOB.

Why not use sed you ask? Because `repex` provides some layers of protection and an easy to use config yaml in which you easily add new files and folders to iterate through.

The layers are:
* Match and only then replace in the matched regular expression which allows the user to provide context for the replacement instead of just iterating through the entire file.
* Check for existing strings in a file before replacing anything.
* Exclude files and folders so that you don't screw up.
* Validate that the replacement went as expected by allowing to execute a validation function post-replacement.

AND, you can use variables (sorta Jinja2 style). How cool is that? See reference config below.


## Installation

`repex` is supported and tested on Python 2.6, 2.7, 3.3+ and PyPy.

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

NOTE: When passing a config file, repex will ignore any options passed which are not `config-only`.

```
$ rpx -h
...

Usage: rpx [OPTIONS] [REGEX_PATH]

  Replace strings in one or multiple files.

  You must either provide `REGEX_PATH` or use the `-c` flag to provide a
  valid repex configuration.

  `REGEX_PATH` can be: a regex of paths under `basedir`, a path to a single
  directory under `basedir`, or a path to a single file.

  It's important to note that if the `REGEX_PATH` is a path to a directory,
  the `-t,--ftype` flag must be provided.

Options:
  -r, --replace TEXT              A regex string to replace. Mutually
                                  exclusive with: [config]
  -w, --replace-with TEXT         Non-regex string to replace with. Mutually
                                  exclusive with: [config]
  -m, --match TEXT                Context regex match for `replace`. If this
                                  is ommited, the context will be the entire
                                  content of the file. Mutually exclusive
                                  with: [config]
  -t, --ftype TEXT                A regex file name to look for. Defaults to
                                  `None`, which means that `PATH_TO_HANDLE`
                                  must be a path to a single file [non-config
                                  only]. Mutually exclusive with: [to_file,
                                  config]
  -b, --basedir TEXT              Where to start looking for `path` from.
                                  Defaults to the cwd. Mutually exclusive
                                  with: [config]
  -x, --exclude-paths TEXT        Paths to exclude when searching for files to
                                  handle. This can be used multiple times.
                                  Mutually exclusive with: [config]
  -i, --must-include TEXT         Files found must include this string. This
                                  can be used multiple times. Mutually
                                  exclusive with: [config]
  --validator TEXT                Validator file:function (e.g.
                                  validator.py:valid_func [non-config only].
                                  Mutually exclusive with: [config]
  --validator-type [per_file|per_type]
                                  Type of validation to perform. `per_type`
                                  will validate the last file found while
                                  `per_file` will run validation for each file
                                  found. Defaults to `per_type` [non-config
                                  only]. Mutually exclusive with: [config]
  --to-file TEXT                  File path to write the output to. Mutually
                                  exclusive with: [ftype, config]
  -c, --config TEXT               Path to a repex config file. Mutually
                                  exclusive with: [REGEX_PATH]
  --vars-file TEXT                Path to YAML based vars file. Mutually
                                  exclusive with: [REGEX_PATH]
  --var TEXT                      A variable to pass to Repex. Can be used
                                  multiple times. Format should be
                                  `'key'='value'`. Mutually exclusive with:
                                  [REGEX_PATH]
  --tag TEXT                      A tag to match with a set of tags in the
                                  config. Can be used multiple times. Mutually
                                  exclusive with: [REGEX_PATH]
  --validate / --no-validate      Validate the config (defaults to True).
                                  Mutually exclusive with: [validate_only,
                                  REGEX_PATH]
  --validate-only                 Only validate the config, do not run
                                  (defaults to False). Mutually exclusive
                                  with: [validate, REGEX_PATH]
  --diff                          Write the diff to a file under `cwd/.rpx
                                  /diff-TIMESTAMP` (defaults to False)
  -v, --verbose                   Show verbose output
  -h, --help                      Show this message and exit.

...

```


#### Using repex like sed

Just like sed:

```bash
rpx /path/to/my/file --replace 3.3 --rwith 3.4
```

Much, much more than sed:

```bash
rpx 'check_validity/resources/.*' 
    -t VERSION \
    -r '3.3.0-m\d+' \
    -w 2.1.1 \
    -i blah -i yay! \
    -x check_validity/resources/VERSION -x another/VERSION \
    --validator check_validity/resources/validator.py:validate \
    --diff -v
```

This will look for all files named "VERSION" under all folders named "check_validity/resources/.*" (recursively); replace all strings matching "3.3.0-m\d+" with "2.1.1"; validate using the "validate" function found in "check_validity/resources/validator.py" only if the files found include the strings "blah" and "yay!" excluding specifically the files "check_validity/resources/VERSION" and "another/VERSION". A git style diff file will be generated.

Note that you must either escape special chars or use single quotes where applicable, that is, where regex strings are provided and bash expansion takes place.

#### Notes

* In complex scenarios, while the CLI can execute repex, it will be more likely that you would use the Python API to execute the `iterate` function as you will most probably want to dynamically pass variables according to certain logic provided by your system.
* Variables provided via the `--var` flag will override variables provided within the `--vars-file`.
* Currently, you can't pass variables which contain a `=` within them.

#### Passing a config file to the CLI

Passing a config file to the CLI is done as follows:

```bash
rpx -c config.yaml -t my_tag -v --vars-file vars.yaml --var 'x'='y' --var 'version'='3.3.0-m3'
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
        diff: true
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
import repex

CONFIG_YAML_FILE = "config.yaml"
VERSION = os.environ['VERSION']  # '3.1.0-m3'

variables = {
    'version': VERSION,
}

repex.iterate(
    config_file_path=CONFIG_YAML_FILE,
    config=None,  # config is simply the dict form of the contents of `CONFIG_YAML_FILE`.
    tags=['my_tag1', 'my_tag2']  # tags to match
    variables=variables,
    validate=True,  # validate config schema
    validate_only=False,  # only validate config schema without running
    with_diff=True  # write the diff to a file
)

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
- `must_include` - as an additional layer of security, you can specify a set of regex based strings to look for to make sure that the files you're dealing with are the actual files you'd like to replace the expressions in.
- `validator` - validator allows you to run a validation function after replacing expressions. It receives `type` which can be either `per_file` or `per_type` where `per_file` runs the validation on every file while `per_type` runs once for every `type` of file; it receives a `path` to the script and a `function` within the script to call. Note that each validation function must return `True` if successful while any other return value will fail the validation. The validating function receives the file's path as and a logger as arguments.
- `diff` - if `true`, will write a git-like unified diff to a file under `cwd/.rpx/diff-TIMESTAMP`. Note that `PATH_REGEX` can be anything which means that the names of the files will look somewhat weird. The diff will be written for each replacement. See below for an example.

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

Variables are one of the strongest features of repex. They provide a way of injecting dynamic info to the config.

Variables can be declared in 4 ways:
- Provided via the CLI
- Provided via the API.
- Harcoded in the config under a top level `variables` section.
- Set as Environment Variables.

Note that variables can also be used within variables in the config.

See the example above for a variable definition reference.

Some important facts about variables:

- Variables with the same name sent via the API will override the hardcoded ones.
- API provided or hardcoded variables can be overriden if env vars exist with the same name but in upper case and prefixed with `REPEX_VAR_` (so the variable "version" can be overriden by an env var called "REPEX_VAR_VERSION".) This can help with, for example, using the $BUILD_NUMBER env var in Jenkins to update a file with the new build number.

Note that if any variables are required but not provided, repex will fail stating that they must be provided.

## Diff

NOTE: THIS IS WIP! Use sparingly.

Repex has the ability to write a git-like unified diff for every replacement that occurs. The diff is written to a file under `cwd/.rpx/` and will contain something that looks like the following:

```text
$ cat .rpx/diff-20170119T115322
...

2017-01-19 11:53:22 tests/resources/multiple/mock_VERSION
0  --- 
1  +++ 
2  @@ -1,7 +1,7 @@
3   {
4     "date": "",
5     "commit": "",
6  -  "version": "3.1.0-m2",
7  +  "version": "xxx",
8     "versiond": "3.1.0-m2",
9     "build": "8"
10  }

2017-01-19 11:53:22 tests/resources/multiple/folders/mock_VERSION
0  --- 
1  +++ 
2  @@ -1,7 +1,7 @@
3   {
4     "date": "",
5     "commit": "",
6  -  "version": "3.1.0-m2",
7  +  "version": "xxx",
8     "versiond": "3.1.0-m2",
9     "build": "8"
10  }

...
```

There is currently no way to ask repex to not generate the diff for every file, so take that into consideration when working with a large amount of files.

Diff generation is off by default. Note that other than providing the overriding `--diff` (or `with_diff` in `iterate`) flag, you can set `diff` for each path in the config.


## Testing

```shell
git clone git@github.com:cloudify-cosmo/repex.git
cd repex
pip install tox
tox
```

## Contributions..

Pull requests are always welcome..
