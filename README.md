repex
=======

`repex` replaces strings in single/multiple files based on regular expressions.

### Installation

Currently, repex is not in pypi, so you'll have to install it directly from Github:

```shell
pip install https://github.com/cloudify-cosmo/repex/archive/master.tar.gz
```

### Usage

Let's say you have files named "VERSION" in different directories which look like this:

```json
{
  "date": "",
  "commit": "",
  "version": "3.1.0-m2",
  "version_other": "3.1.2-m1",
  "build": "8"
}
```

And you'd like to replace 3.1.0-m2 with 3.1.0-m3 in all of those files

You would create a repex config.yaml with the following:

```yaml
variables:
    version: 3.1.0m3

paths:
    -   type: VERSION
        path: repex/tests/resources/
        base_directory: repex/tests/resources/
        match: '"version": "\d+\.\d+(\.\d+)?(-\w\d+)?'
        replace: \d+\.\d+(\.\d+)?(-\w\d+)?
        with: "{{ .version }}"
        validate_before: true
        must_include:
            - date
            - commit
            - version
```

and do the following

```python

import os
from repex.repex import iterate

VERSION = os.environ['VERSION'] # '3.1.0-m3'

variables = {
    'version': VERSION
}

iterate(CONFIG_YAML_FILE, variables)
```

#### Config yaml Explained

- `variables` is a dict of variables you can use throughout the config (using the API, you can also send the dictionary rather the hard code it into the config.yaml, which is obviously the more common use case.) `path`, `match`, `replace` and `with` can all receive variables.
- `type` is the files name you'd like to look for.
- `path` is a regex path in which you'd like to search for files (so, for instance, if you only want to replace files in directory names starting with "my-", you would write "my-.*")
- `base_directory` is the directory from which you'd like to start the recursive search for files.
- `match` is the initial regex based string you'd like to match before replacing the expression. This provides a more robust way to replace strings where you first match the exact area in which you'd like to replace the expression and only then match the expression you want to replace within it. It also provides a way to replace only specific instances of an expression, and not all.
- `replace` - which regex expression would you like to replace?
- `with` - what you replace with.
- `validate_before` - a flag stating that you'd like to validate that the pattern you're looking for exists in the file and that all strings in `must_include` exists in the file as well.
- `must_include` - as an additional layer of security, you can specify a set of regex based strings to look for to make sure that the files you're dealing with are the actual files you'd like to replace the expressions in.

In case you're providing a path to a file rather than a directory:

- `type` and `base_directory` are depracated
- you can provide a `to_file` key with the path to the file you'd like to create after replacing.

#### Basic Functions

3 basic functions are provided:

- `iterate` - receives the config yaml file and the variables dict and iterates through the config file's `paths` dict destroying everything that comes in its path :)
- `handle_path` - receives one of the objects in the `paths` dict in the config yaml file and the variables dict, finds all files, and processes them (is used by `iterate`).
- `handle_file` - receives one of the objects in the `paths` dict in the config yaml file and the variables dict, and processes the specific file specified in the `path` key (used by `handle_path`).