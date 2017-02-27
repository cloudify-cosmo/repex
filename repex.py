########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import re
import sys
import imp
import time
import shutil
import logging
import difflib
from datetime import datetime

import yaml
import click
import jsonschema


ERRORS = {
    'invalid_yaml': '`config` must be a valid repex config in YAML form',
    'no_config_supplied':
        'Either `config` or `config_file_path` must be supplied',
    'variables_not_dict': '`variables` must be of type dict',
    'tags_not_list': '`tags` must be of type list',
    'config_file_not_found': 'Could not open config file',
    'string_failed_to_expand': 'String failed to expand',
    'file_not_found': 'File not found',
    'type_path_collision': 'If `type` is specified, `path` must not be a '
                           'path to a single file.',
    'to_file_requires_explicit_path': '`to_file` requires an explicit single '
                                      'file `path`',
    'prevalidation_failed': 'Prevalidation failed. Some required strings were '
                            'not found',
    'validation_failed': 'Validation failed!',
    'validator_path_not_found': 'Path to validator script not found',
    'validator_function_not_found': 'Validation function not found in script'
}


_REPEX_VAR_PREFIX = 'REPEX_VAR_'


def setup_logger():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger('repex')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logger()


def set_verbose():
    logger.setLevel(logging.DEBUG)


def _import_yaml(config_file_path):
    """Return a configuration object
    """
    try:
        logger.info('Importing config %s...', config_file_path)
        with open(config_file_path) as config_file:
            return yaml.safe_load(config_file.read())
    except IOError as ex:
        raise RepexError('{0}: {1} ({2})'.format(
            ERRORS['config_file_not_found'], config_file_path, ex))
    except (yaml.parser.ParserError, yaml.scanner.ScannerError) as ex:
        raise RepexError('{0} ({1})'.format(ERRORS['invalid_yaml'], ex))


def _get_config(config_file_path=None, config=None):
    if not (config or config_file_path):
        raise RepexError(ERRORS['no_config_supplied'])

    if config_file_path:
        config = _import_yaml(config_file_path)

    config = config or {}
    config['variables'] = config.get('variables', {})
    return config


def _normalize_excluded_paths(base_dir, excluded_paths):
    excluded_paths = excluded_paths or []
    excluded_paths = [os.path.join(base_dir, excluded_path).rstrip('/')
                      for excluded_path in excluded_paths]
    return excluded_paths


def _set_match_parameters(filename,
                          filepath,
                          filename_regex,
                          excluded_filename_regex,
                          excluded_paths):
    filename_regex = r'{0}'.format(filename_regex)
    excluded_filename_regex = r'{0}'.format(excluded_filename_regex)

    is_file = os.path.isfile(filepath)
    matched = re.match(filename_regex, filename)
    excluded_filename = re.match(excluded_filename_regex, filename)
    excluded_path = filepath in excluded_paths
    return is_file, matched, excluded_filename, excluded_path


def _get_all_files(filename_regex,
                   path,
                   base_dir,
                   excluded_paths=None,
                   excluded_filename_regex=None):
    """Get all files for processing.

    This starts iterating from `base_dir` and checks for all files
    that look like `filename_regex` under `path` regex excluding
    all paths under the `excluded_paths` list, whether they are files
    or folders. `excluded_paths` are explicit paths, not regex.
    `excluded_filename_regex` are files to be excluded as well.
    """
    # For windows
    def replace_backslashes(string):
        return string.replace('\\', '/')

    excluded_paths = _normalize_excluded_paths(base_dir, excluded_paths)
    if excluded_paths:
        logger.info('Excluding paths: %s', excluded_paths)

    logger.info('Looking for %s under %s...',
                filename_regex, os.path.join(base_dir, path))
    if excluded_filename_regex:
        logger.info('Excluding file names: %s', excluded_filename_regex)

    path_expression = re.compile(replace_backslashes(path))

    target_files = []

    for root, _, files in os.walk(base_dir):
        if not root.startswith(tuple(excluded_paths)) \
                and path_expression.search(replace_backslashes(root)):
            for filename in files:
                filepath = os.path.join(root, filename)
                is_file, matched, excluded_filename, excluded_path = \
                    _set_match_parameters(
                        filename,
                        filepath,
                        filename_regex,
                        excluded_filename_regex,
                        excluded_paths)
                if is_file and matched and not excluded_filename \
                        and not excluded_path:
                    logger.debug('%s is a match. Appending to list...',
                                 filepath)
                    target_files.append(filepath)
    return target_files


class _Validator(object):
    def __init__(self, validator_config):
        self.validation_type = validator_config.get('type', 'per_file')
        self.validator_path = validator_config.get('path')
        self.validation_function = validator_config.get('function')
        self._validate_config()

    def validate(self, file_to_validate):
        validator = self._import_validator()
        if not hasattr(validator, self.validation_function):
            raise RepexError(ERRORS['validator_function_not_found'])

        logger.info('Validating %s using %s:%s...',
                    file_to_validate,
                    self.validator_path,
                    self.validation_function)
        # TODO: self.validation_function might be a variable, not a function.
        # We should try here.
        validated = getattr(validator, self.validation_function)(
            file_to_validate, logger)
        if validated:
            logger.info('Validation Succeeded for: %s', file_to_validate)
            return True
        else:
            return False

    def _validate_config(self):
        if not os.path.isfile(self.validator_path):
            raise RepexError(ERRORS['validator_path_not_found'])

    def _import_validator(self):
        logger.debug('Importing validator: %s', self.validator_path)
        return imp.load_source(
            os.path.basename(self.validator_path), self.validator_path)


class _VariablesHandler(object):
    """Handle variable expansion and replacement

    For every field in a path object, look for {{ .\.+ }}.
    For every result, try to replace it with one of the variable values
    supplied.
    If, eventually, there are still {{ .\.+ }} in the field, raise.
    """

    _variable_string_expression = re.compile(r'{{ \..+? }}')

    def expand(self, repex_vars, fields):
        r"""Receive a dict of variables and a dict of fields
        and iterates through them to expand a variable in an field, then
        returns the fields dict with its variables expanded.

        This will fail if not all variables expand (due to not providing
        all necessary ones).

        fields:

        type: VERSION
        path: resources
        excluded:
            - excluded_file.file
        base_directory: '{{ .base_dir }}'
        match: '"version": "\d+\.\d+(\.\d+)?(-\w\d+)?'
        replace: \d+\.\d+(\.\d+)?(-\w\d+)?
        with: "{{ .version }}"
        must_include:
            - {{ .my_var }}/{{ .another_var }}
            - {{ .my_other_var }}
            - version
        validator:
            type: per_file
            path: {{ .my_validator_path }}
            function: validate

        variables:

        {
            'version': 3,
            'base_dir': .
            ...
        }

        :param dict vars: dict of variables
        :param dict fields: dict of fields as shown above.
        """
        logger.debug('Expanding variables...')

        unexpanded_instances = set()

        # Expand variables in variables
        # TODO: This should be done in the global scope.
        # _VariableHandler is called per path, which makes this redundant
        # as variables are declared globally per config.
        for k, v in repex_vars.items():
            repex_vars[k] = self._expand_var(v, repex_vars)
            instances = self._get_instances(repex_vars[k])
            unexpanded_instances.update(instances)

        # TODO: Consolidate variable expansion code into single logic
        # Expand variables in path objects
        for key in fields.keys():
            field = fields[key]
            if isinstance(field, str):
                fields[key] = self._expand_var(field, repex_vars)
                instances = self._get_instances(fields[key])
                unexpanded_instances.update(instances)
            elif isinstance(field, dict):
                for k, v in field.items():
                    fields[key][k] = self._expand_var(v, repex_vars)
                    instances = self._get_instances(fields[key][k])
                    unexpanded_instances.update(instances)
            elif isinstance(field, list):
                for index, item in enumerate(field):
                    fields[key][index] = self._expand_var(item, repex_vars)
                    instances = self._get_instances(fields[key][index])
                    unexpanded_instances.update(instances)

        if unexpanded_instances:
            raise RepexError(
                'Variables failed to expand: {0}\n'
                'Please make sure to provide all necessary variables '.format(
                    list(unexpanded_instances)))

        return fields

    @staticmethod
    def _get_variable_string(variable):
        return '{{ ' + '.{0}'.format(variable) + ' }}'

    def _get_instances(self, string):
        return re.findall(self._variable_string_expression, string)

    def _expand_var(self, in_string, available_variables):
        """Expand variable to its corresponding value in_string

        :param string variable: variable name
        :param value: value to replace with
        :param string in_string: the string to replace in
        """
        instances = self._get_instances(in_string)
        for instance in instances:
            for name, value in available_variables.items():
                variable_string = self._get_variable_string(name)
                if instance == variable_string:
                    in_string = in_string.replace(variable_string, value)
        return in_string


def _merge_variables(vars_from_config, variables):
    repex_vars = {}
    repex_vars.update(vars_from_config)
    repex_vars.update(variables)
    for var, value in os.environ.items():
        if var.startswith(_REPEX_VAR_PREFIX):
            repex_vars[var.replace(_REPEX_VAR_PREFIX, '').lower()] = value
    return repex_vars


def _match_tags(repex_tags, path_tags):
    """Check for matching tags between what the user provided
    and the tags set in the config.

    If `any` is chosen, match.
    If no tags are chosen and none are configured, match.
    If the user provided tags match any of the configured tags, match.
    """
    if 'any' in repex_tags or (not repex_tags and not path_tags):
        return True
    elif set(repex_tags) & set(path_tags):
        return True
    return False


def iterate(config_file_path=None,
            config=None,
            variables=None,
            tags=None,
            validate=True,
            validate_only=False,
            with_diff=False):
    """Iterate over all paths in `config_file_path`

    :param string config_file_path: a path to a repex config file
    :param dict config: a dictionary representing a repex config
    :param dict variables: a dict of variables (can be None)
    :param list tags: a list of tags to check for
    :param bool validate: whether to perform schema validation on the config
    :param bool validate_only: only perform validation without running
    :param bool with_diff: whether to write a diff of all changes to a file
    """
    # TODO: Check if tags can be a tuple instead of a list
    if not isinstance(variables or {}, dict):
        raise TypeError(ERRORS['variables_not_dict'])
    if not isinstance(tags or [], list):
        raise TypeError(ERRORS['tags_not_list'])

    config = _get_config(config_file_path, config)
    if validate or validate_only:
        _validate_config_schema(config)
    if validate_only:
        logger.info('Config file validation completed successfully!')
        sys.exit(0)

    repex_vars = _merge_variables(config['variables'], variables or {})
    repex_tags = tags or []
    logger.debug('Chosen tags: %s', repex_tags)

    for path in config['paths']:
        _process_path(path, repex_tags, repex_vars, with_diff)


def _process_path(path, repex_tags, repex_vars, with_diff):
    path_tags = path.get('tags', [])
    logger.debug('Checking for matching tags: %s', path_tags)
    tags_match = _match_tags(repex_tags, path_tags)
    if tags_match:
        logger.debug('Matching tag(s) found for path: %s...', path)
        handle_path(path, repex_vars, with_diff)
    else:
        logger.debug('No matching tags found for path: %s. Skipping...',
                     path)


def _get_current_time():
    """Return a human readable unix timestamp formatted string

    e.g. 2015-06-11 10:10:01
    """
    return datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')


def _get_file_contents(path):
    with open(path) as open_file:
        return open_file.readlines()


def _normalize_current_time(current_time):
    timestamp = current_time.replace('-', '')
    timestamp = timestamp.replace(':', '')
    timestamp = timestamp.split(' ')
    return 'T'.join(timestamp)


def _write_diff(pre, post, output_file_path):
    diff = difflib.unified_diff(pre, post)
    items = [line for line in diff]
    line_num = len(str(len(items)))

    if not os.path.isdir(_DIFF_HOME) and items:
        os.makedirs(_DIFF_HOME)

    if items:
        with open(_DIFF_FILE_PATH, 'a+') as diff_log:
            diff_log.write(_get_current_time() + ' ' + output_file_path)
            diff_log.write('\n')
            for index, line in enumerate(items):
                diff_log.write('{0:{1}} {2}'.format(
                    str(index), line_num, line))
            diff_log.write('\n\n')


def _assert_validated(validator, file_to_validate):
    if not validator.validate(file_to_validate):
        raise RepexError(ERRORS['validation_failed'])


def _handle_single_file(rpx,
                        path_to_handle,
                        pathobj,
                        validate,
                        diff,
                        validator=None):
    if os.path.isfile(path_to_handle):
        if pathobj.get('diff') or diff:
            pre = _get_file_contents(path_to_handle)
            output_file_path = rpx.handle_file(path_to_handle)
            post = _get_file_contents(output_file_path)
            _write_diff(pre, post, output_file_path)
        else:
            rpx.handle_file(path_to_handle)
        if validate:
            _assert_validated(validator, path_to_handle)
    else:
        raise RepexError('{0}: {1}'.format(
            ERRORS['file_not_found'], path_to_handle))


def _handle_multiple_files(rpx,
                           path_to_handle,
                           pathobj,
                           validate,
                           diff,
                           validator=None,
                           validator_type=None):
    if os.path.isfile(path_to_handle):
        raise RepexError(ERRORS['type_path_collision'])
    if pathobj.get('to_file'):
        raise RepexError(ERRORS['to_file_requires_explicit_path'])

    files = _get_all_files(
        pathobj['type'],
        pathobj['path'],
        pathobj['base_directory'],
        pathobj['excluded']
    )

    for file_to_handle in files:
        if pathobj.get('diff') or diff:
            pre = _get_file_contents(file_to_handle)
            output_file_path = rpx.handle_file(file_to_handle)
            post = _get_file_contents(output_file_path)
            _write_diff(pre, post, output_file_path)
        else:
            rpx.handle_file(file_to_handle)
        if validate and validator_type == 'per_file':
            _assert_validated(validator, file_to_handle)

    # Need to check that `files` isn't an empty list or `file_to_handle`
    # will be undefined.
    if files and file_to_handle and validate and \
            validator_type == 'per_type':
        _assert_validated(validator, file_to_handle)


def _set_path_defaults(pathobj):
    pathobj['base_directory'] = pathobj.get('base_directory', os.getcwd())
    pathobj['match'] = pathobj.get('match', pathobj['replace'])
    pathobj['to_file'] = pathobj.get('to_file', False)
    pathobj['must_include'] = pathobj.get('must_include', [])
    pathobj['excluded'] = pathobj.get('excluded', [])
    return pathobj


def handle_path(pathobj, variables=None, diff=False):
    """Iterate over all chosen files in a path

    :param dict pathobj: a dict of a specific path in the config
    :param dict variables: a dict of variables (can be None)
    """
    logger.info('Handling path with description: %s',
                pathobj.get('description'))

    variables = variables or {}
    variable_expander = _VariablesHandler()
    pathobj = variable_expander.expand(variables, pathobj)

    pathobj = _set_path_defaults(pathobj)

    path_to_handle = os.path.join(pathobj['base_directory'], pathobj['path'])
    logger.debug('Path to process: %s', path_to_handle)

    validate = 'validator' in pathobj
    if validate:
        validator_config = pathobj['validator']
        validator = _Validator(validator_config)
        validator_type = validator_config.get('type', 'per_type')

    rpx = Repex(pathobj)

    if not pathobj.get('type'):
        _handle_single_file(
            rpx=rpx,
            path_to_handle=path_to_handle,
            pathobj=pathobj,
            validate=validate,
            diff=diff,
            validator=validator if validate else None)
    else:
        _handle_multiple_files(
            rpx=rpx,
            path_to_handle=path_to_handle,
            pathobj=pathobj,
            validate=validate,
            diff=diff,
            validator=validator if validate else None,
            validator_type=validator_type if validate else None)


class Repex(object):
    def __init__(self, pathobj):
        # Ideally, we're receive **pathobj instead, but it contains a `with`
        # key which makes it impossible.
        self.match_regex = pathobj['match']
        self.pattern_to_replace = pathobj['replace']
        self.match_expression = \
            re.compile('(?P<matchgroup>{0})'.format(pathobj['match']))
        self.replace_expression = re.compile(self.pattern_to_replace)

        self.replace_with = pathobj['with']
        self.to_file = pathobj['to_file']
        self.must_include = pathobj['must_include']

    def handle_file(self, file_to_handle):
        with open(file_to_handle) as f:
            content = f.read()

        if self.must_include and not \
                self.validate_before(content, file_to_handle):
            raise RepexError(ERRORS['prevalidation_failed'])

        replacements_found = False
        output_file_path = self._init_file(file_to_handle)
        matches = self.find_matches(content, file_to_handle)
        logger.info(
            'Replacing all strings that match %s and are contained in '
            '%s with %s...', self.pattern_to_replace, self.match_regex,
            self.replace_with)
        for match in matches:
            if self.is_in_string(match):
                replacements_found = True
                content = self.replace(match, content)
        if not replacements_found:
            logger.info('Found nothing to replace within matches')
        if matches:
            self._write_final_content(content, output_file_path)
        else:
            os.remove(output_file_path + '.repex.tmp')
        return output_file_path

    def validate_before(self, content, file_to_handle):
        """Verify that all required strings are in the file
        """
        logger.debug('Looking for required strings: %s', self.must_include)
        included = True
        for string in self.must_include:
            if not re.search(r'{0}'.format(string), content):
                logger.error('Required string `%s` not found in %s',
                             string, file_to_handle)
                included = False
        if not included:
            logger.debug('Required strings not found')
            return False
        logger.debug('Required strings found')
        return True

    def find_matches(self, content, file_to_handle):
        """Find all matches of an expression in a file
        """
        # look for all match groups in the content
        groups = [match.groupdict() for match in
                  self.match_expression.finditer(content)]
        # filter out content not in the matchgroup
        matches = [group['matchgroup'] for group in groups
                   if group.get('matchgroup')]

        logger.info('Found %s matches in %s', len(matches), file_to_handle)
        # We only need the unique strings found as we'll be replacing each
        # of them. No need to replace the ones already replaced.
        return list(set(matches))

    def is_in_string(self, match):
        return True if self.replace_expression.search(match) else False

    def replace(self, match, content):
        """Replace all occurences of the regex in all matches
        from a file with a specific value.
        """
        new_string = self.replace_expression.sub(self.replace_with, match)
        logger.info('Replacing: [ %s ] --> [ %s ]', match, new_string)
        new_content = content.replace(match, new_string)
        return new_content

    def _init_file(self, file_to_handle):
        temp_file_path = file_to_handle + '.repex.tmp'
        output_file_path = self.to_file if self.to_file else file_to_handle
        if not self.to_file:
            shutil.copy2(output_file_path, temp_file_path)
        return output_file_path

    def _write_final_content(self, content, output_file_path):
        temp_file_path = output_file_path + '.repex.tmp'
        if self.to_file:
            logger.info('Writing output to %s...', output_file_path)
        else:
            logger.debug('Writing output to %s...', output_file_path)
        with open(temp_file_path, "w") as temp_file:
            temp_file.write(content)
        shutil.move(temp_file_path, output_file_path)


def _validate_config_schema(config):
    schema = {
        'type': 'object',
        'properties': {
            'variables': {'type': 'object'},
            'paths': {
                'type': 'array',
                'items': [
                    {
                        'type': 'object',
                        'properties': {
                            'type': {'type': 'string'},
                            'description': {'type': 'string'},
                            'path': {'type': 'string'},
                            'excluded': {'type': 'array'},
                            'base_directory': {'type': 'string'},
                            'match': {'type': 'string'},
                            'replace': {'type': 'string'},
                            'with': {'type': 'string'},
                            'to_file': {'type': 'string'},
                            'must_include': {'type': 'array'},
                            'tags': {'type': 'array'},
                            'validator': {
                                'type': 'object',
                                'properties': {
                                    'type': {'enum': ['per_type', 'per_file']},
                                    'path': {'type': 'string'},
                                    'function': {'type': 'string'}
                                },
                                'required': ['path', 'function'],
                                "additionalProperties": False
                            }
                        },
                        # TODO: `match` should not be required and should
                        # default to `replace`
                        'required': ['path', 'match', 'replace', 'with'],
                        "additionalProperties": False
                    }
                ]
            }
        },
        'required': ['paths'],
        "additionalProperties": False
    }
    logger.info('Validating configuration...')
    try:
        jsonschema.validate(config, schema)
    except jsonschema.exceptions.ValidationError as ex:
        raise RepexError(ex)


class RepexError(Exception):
    pass


def _build_vars_dict(vars_file='', variables=None):
    """Merge variables into a single dictionary

    Applies to CLI provided variables only
    """
    repex_vars = {}
    if vars_file:
        with open(vars_file) as varsfile:
            repex_vars = yaml.safe_load(varsfile.read())
    for var in variables:
        key, value = var.split('=')
        repex_vars.update({str(key): str(value)})
    return repex_vars


class _MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        self.mutuality_string = ', '.join(self.mutually_exclusive)
        if self.mutually_exclusive:
            help_text = kwargs.get('help', '')
            kwargs['help'] = (
                '{0}. Mutually exclusive with: [{1}]'.format(
                    help_text, self.mutuality_string))
        super(_MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{0}` is mutually exclusive with "
                "arguments `{1}`.".format(self.name, self.mutuality_string))
        return super(_MutuallyExclusiveOption, self).handle_parse_result(
            ctx, opts, args)


_DIFF_HOME = os.path.join(os.getcwd(), '.rpx')
_NORMALIZED_TIMESTAMP = _normalize_current_time(_get_current_time())
_DIFF_FILE_PATH = os.path.join(_DIFF_HOME, 'diff-{0}'.format(
    _NORMALIZED_TIMESTAMP))
CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())


@click.command(context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument('REGEX_PATH', required=False)
@click.option('-r',
              '--replace',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              help='A regex string to replace')
@click.option('-w',
              '--replace-with',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              help='Non-regex string to replace with')
@click.option('-m',
              '--match',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              help='Context regex match for `replace`. '
                   'If this is ommited, the context will be the '
                   'entire content of the file')
@click.option('-t',
              '--ftype',
              default=None,
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config', 'to_file'],
              help='A regex file name to look for. '
                   'Defaults to `None`, which means that '
                   '`PATH_TO_HANDLE` must be a path to a single file '
                   '[non-config only]')
@click.option('-b',
              '--basedir',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              default=os.getcwd(),
              help='Where to start looking for `path` from. '
                   'Defaults to the cwd')
@click.option('-x',
              '--exclude-paths',
              multiple=True,
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              help='Paths to exclude when searching for files to handle. '
                   'This can be used multiple times')
@click.option('-i',
              '--must-include',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              multiple=True,
              help='Files found must include this string. '
                   'This can be used multiple times')
@click.option('--validator',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              help='Validator file:function (e.g. validator.py:valid_func '
                   '[non-config only]')
@click.option('--validator-type',
              default='per_type',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config'],
              type=click.Choice(['per_file', 'per_type']),
              help='Type of validation to perform. `per_type` will validate '
                   'the last file found while `per_file` will run validation '
                   'for each file found. Defaults to `per_type` '
                   '[non-config only]')
@click.option('--to-file',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['config', 'ftype'],
              help='File path to write the output to')
@click.option('-c',
              '--config',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH'],
              type=click.STRING,
              help='Path to a repex config file')
@click.option('--vars-file',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH'],
              help='Path to YAML based vars file')
@click.option('--var',
              multiple=True,
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH'],
              help="A variable to pass to Repex. Can be used multiple times. "
                   "Format should be `'key'='value'`")
@click.option('--tag',
              multiple=True,
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH'],
              help='A tag to match with a set of tags in the config. '
                   'Can be used multiple times')
@click.option('--validate/--no-validate',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH', 'validate_only'],
              default=True,
              help='Validate the config (defaults to True)')
@click.option('--validate-only',
              cls=_MutuallyExclusiveOption,
              mutually_exclusive=['REGEX_PATH', 'validate'],
              default=False,
              is_flag=True,
              help='Only validate the config, do not run (defaults to False)')
@click.option('--diff',
              default=False,
              is_flag=True,
              help='Write the diff to a file under `cwd/.rpx/diff-TIMESTAMP` '
                   '(defaults to False)')
@click.option('-v',
              '--verbose',
              default=False,
              is_flag=True,
              help='Show verbose output')
def main(verbose, **kwargs):
    """Replace strings in one or multiple files.

    You must either provide `REGEX_PATH` or use the `-c` flag
    to provide a valid repex configuration.

    `REGEX_PATH` can be: a regex of paths under `basedir`,
    a path to a single directory under `basedir`,
    or a path to a single file.

    It's important to note that if the `REGEX_PATH` is a path to a
    directory, the `-t,--ftype` flag must be provided.
    """
    config = kwargs['config']

    if not config and not kwargs['regex_path']:
        click.echo('Must either provide a path or a viable repex config file.')
        sys.exit(1)

    if verbose:
        set_verbose()

    if config:
        repex_vars = _build_vars_dict(kwargs['vars_file'], kwargs['var'])
        try:
            iterate(
                config_file_path=config,
                variables=repex_vars,
                tags=list(kwargs['tag']),
                validate=kwargs['validate'],
                validate_only=kwargs['validate_only'],
                with_diff=kwargs['diff'])
        except (RepexError, IOError, OSError) as ex:
            sys.exit(str(ex))
    else:
        pathobj = _construct_path_object(**kwargs)
        try:
            handle_path(pathobj)
        except (RepexError, IOError, OSError) as ex:
            sys.exit(str(ex))


def _construct_path_object(**kwargs):
    ftype = kwargs['ftype']
    match = kwargs['match']

    pathobj = {
        'type': r'{0}'.format(ftype) if ftype else None,
        'path': r'{0}'.format(kwargs['regex_path']),
        'to_file': kwargs['to_file'],
        'base_directory': kwargs['basedir'],
        'match': r'{0}'.format(match) if match else kwargs['replace'],
        'replace': r'{0}'.format(kwargs['replace']),
        'with': kwargs['replace_with'],
        'excluded': list(kwargs['exclude_paths']),
        'must_include': list(kwargs['must_include']),
        'diff': kwargs['diff']
    }
    validator = kwargs['validator']
    if validator:
        validator_path, validator_function = validator.split(':')
        pathobj['validator'] = {
            'type': kwargs['validator_type'],
            'path': validator_path,
            'function': validator_function
        }
    return pathobj
