import os
import re
import sys
import imp
import shutil
import logging

import yaml
import click

from . import logger, codes


DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_VALIDATE_BEFORE = True
DEFAULT_VALIDATE_AFTER = False
DEFAULT_MUST_INCLUDE = []
REPEX_VAR_PREFIX = 'REPEX_VAR_'

lgr = logger.init()


def _set_global_verbosity_level(is_verbose_output=False):
    if is_verbose_output:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)


def import_config(config_file):
    """Returns a configuration object

    :param string config_file: path to config file
    """
    try:
        lgr.info('Importing config {0}...'.format(config_file))
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        lgr.error(ex.message)
        lgr.error('Cannot access config file')
        sys.exit(codes.mapping['cannot_access_config_file'])
    except (yaml.parser.ParserError, yaml.scanner.ScannerError) as ex:
        lgr.error(ex.message)
        lgr.error('Invalid yaml file')
        sys.exit(codes.mapping['invalid_yaml_file'])


def get_all_files(file_name_regex, path, base_dir, excluded_paths=None,
                  verbose=False, exclude_file_name_regex=None):
    """Get all files for processing.

    This starts iterating from `base_dir` and checks for all files
    that look like `file_name_regex` under `path` regex excluding
    all paths under the `excluded_paths` list, whether they are files
    or folders. `excluded_paths` are explicit paths, not regex.
    `exclude_file_name_regex` are files to be excluded as well.
    """
    _set_global_verbosity_level(verbose)

    excluded_paths = excluded_paths if excluded_paths else []
    if not isinstance(excluded_paths, list):
        lgr.error('Excluded_paths must be of type list (not {0})'.format(
            type(excluded_paths)))
        sys.exit(codes.mapping['excluded_paths_must_be_a_list'])
    excluded_paths = [os.path.join(base_dir, excluded_path).rstrip('/')
                      for excluded_path in excluded_paths]
    lgr.info('Excluded paths: {0}'.format(excluded_paths))

    lgr.info('Looking for {0}\'s under {1} in {2}...'.format(
        file_name_regex, path, base_dir))
    if exclude_file_name_regex:
        lgr.info('Excluding all files named: {0}'.format(
            exclude_file_name_regex))
    target_files = []

    def replace_backslashes(string):
        return string.replace('\\', '/')

    for root, _, files in os.walk(base_dir):
        # for each folder in root, check if it begins with one of excluded_path
        if not root.startswith(tuple(excluded_paths)) \
                and re.search(r'{0}'.format(
                    replace_backslashes(path)), replace_backslashes(root)):
            for f in files:
                file_path = os.path.join(root, f)
                is_file = os.path.isfile(file_path)
                matched = re.match(r'{0}'.format(file_name_regex), f)
                excluded = re.match(r'{0}'.format(exclude_file_name_regex), f)
                if is_file and matched and not excluded \
                        and file_path not in excluded_paths:
                    lgr.debug('{0} is a match. Appending to '
                              'list...'.format(file_path))
                    target_files.append(file_path)
    lgr.debug('Files to handle: {0}'.format(target_files))
    return target_files


class Validator():
    def __init__(self, validator_config):
        self.config = validator_config
        self._validate_config()

    def validate(self, path_to_validate):
        validator = self._import_validator(self.config['path'])
        lgr.info('Validating {0} using {1}:{2}...'.format(
            path_to_validate, self.config['path'], self.config['function']))
        validated = getattr(
            validator, self.config['function'])(path_to_validate, lgr)
        if validated is not True:
            lgr.error('Failed to validate: {0}'.format(path_to_validate))
            sys.exit(codes.mapping['validator_failed'])
        lgr.info('Validation Succeeded for: {0}...'.format(path_to_validate))

    def _validate_config(self):
        validator_type = self.config.get('type') or 'per_type'
        validator_types = ('per_file', 'per_type')
        if validator_type not in validator_types:
            lgr.error('Invalid validator type. Can be one of {0}.'.format(
                validator_types))
            sys.exit(codes.mapping['invalid_validator_type'])
        if not self.config.get('path'):
            lgr.error('`path` to validator script must be supplied in '
                      'validator config.')
            sys.exit(codes.mapping['validator_path_missing'])
        if not self.config.get('function'):
            lgr.error('Validation `function` to use must be supplied in '
                      'validator config.')
            sys.exit(codes.mapping['validator_path_missing'])

    @staticmethod
    def _import_validator(validator_path):
        lgr.debug('Importing validator: {0}'.format(validator_path))
        if not os.path.isfile(validator_path):
            lgr.error('Validator script: {0} does not exist.'.format(
                validator_path))
            sys.exit(codes.mapping['validator_script_missing'])
        return imp.load_source(
            os.path.basename(validator_path), validator_path)


class VarHandler():
    """Handles variable expansion and replacement
    """
    def __init__(self, verbose=False):
        _set_global_verbosity_level(verbose)

    def expand(self, repex_vars, attributes):
        """Receives a list of variables and a dict of attributes
        and iterates through them to expand a variable in an attribute

        attributes:

        type: VERSION
        path: resources
        excluded:
            - excluded_file.file
        base_directory: '{{ .base_dir }}'
        match: '"version": "\d+\.\d+(\.\d+)?(-\w\d+)?'
        replace: \d+\.\d+(\.\d+)?(-\w\d+)?
        with: "{{ .version }}"
        validate_before: true
        must_include:
            - date
            - commit
            - version

        variables:

        {
            'version': 3,
            'base_dir': .
        }

        Will only replace in attributes of type `string`. So, for instance,
        the values in `excluded`, `must_include` and `validate_before`
        will not be replaced.

        :param dict vars: dict of variables
        :param dict attributes: dict of attributes as shown above.
        """
        lgr.debug('Expanding variables...')
        for var, value in repex_vars.items():
            for attribute in attributes.keys():
                obj = attributes[attribute]
                if isinstance(obj, basestring):
                    # TODO: Handle cases where var is referenced
                    # TODO: but not defined
                    attributes[attribute] = \
                        self._expand_var(var, value, obj)
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        attributes[attribute][k] = \
                            self._expand_var(var, value, v)
                elif isinstance(obj, list):
                    for item in obj:
                        index = obj.index(item)
                        attributes[attribute][index] = \
                            self._expand_var(var, value, item)
        return attributes

    def _expand_var(self, variable, value, in_string):
        """Expands variable to its corresponding value in_string

        :param string variable: variable name
        :param value: value to replace with
        :param string in_string: the string to replace in
        """
        var_string = '{{ ' + '.{0}'.format(variable) + ' }}'

        def check_if_expanded(string, variable):
            lgr.debug('Verifying that string {0} expanded'.format(
                string))
            if re.search(var_string, string):
                return False
            return True

        if re.search(var_string, in_string):
            lgr.debug('Expanding var {0} to {1} in {2}'.format(
                variable, value, in_string))
            expanded_variable = re.sub(var_string, str(value), in_string)
            if not check_if_expanded(expanded_variable, variable):
                lgr.error('String {0} failed to expand.'.format(
                    expanded_variable))
                sys.exit(codes.mapping['string_failed_to_expand'])
            return expanded_variable
        return in_string


def iterate(config, variables=None, verbose=False, tags=None):
    """Iterates over all paths in `configfile`

    If user chose tags and path has tags run only if matching tags found
    If user chose tags and path does not have tags do not run on path
    If user did not choose tags and path has tags do not run on path
    If user did not choose tags and path does not have tags run on path
    If user chose 'any' tags run on path

    :param string configfile: yaml path with files to iterate over
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)

    if os.path.isfile(str(config)):
        config = import_config(config)
    elif not isinstance(config, dict):
        raise RuntimeError('`config` must either be a valid repex config '
                           'dict or a path to a file.')

    variables = variables or {}
    if not isinstance(variables, dict):
        raise RuntimeError('`variables` must be of type dict.')

    try:
        paths = config['paths']
    except TypeError:
        lgr.error('No paths configured in yaml.')
        sys.exit(codes.mapping['no_paths_configured'])

    repex_vars = config.get('variables', {})
    repex_vars.update(variables)
    for var, value in os.environ.items():
        if var.startswith(REPEX_VAR_PREFIX):
            repex_vars[var.replace(REPEX_VAR_PREFIX, '').lower()] = value
    lgr.debug('Variables: {0}'.format(repex_vars))

    user_selected_tags = tags or []
    if not isinstance(user_selected_tags, list):
        raise RuntimeError('tags must be of type list.')
    lgr.debug('User tags: {0}'.format(user_selected_tags))

    for path in paths:
        path_tags = path.get('tags', [])
        lgr.debug('Checking user tags against path tags: {0}'.format(
            path_tags))
        if 'any' in user_selected_tags or \
                (not user_selected_tags and not path_tags):
            handle_path(path, repex_vars, verbose)
        else:
            if set(user_selected_tags) & set(path_tags):
                lgr.debug('Matching tag(s) found for path: '
                          '{0}...'.format(path))
                handle_path(path, repex_vars, verbose)
            else:
                lgr.debug('No matching tags found for path: '
                          '{0}, skipping...'.format(path))


def handle_path(path_dict, variables=None, verbose=False):
    """Iterates over all files in path_dict['path']

    :param dict path_dict: a dict of a specific path in the config
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    if variables:
        var_expander = VarHandler(verbose)
        path_dict = var_expander.expand(variables, path_dict)
    path_dict['base_directory'] = path_dict.get('base_directory', '')
    lgr.debug('path to process: {0}'.format(
        os.path.join(path_dict['base_directory'], path_dict['path'])))
    path_to_handle = os.path.join(
        path_dict['base_directory'], path_dict['path'])

    validate = 'validator' in path_dict
    if validate:
        validator_config = path_dict['validator']
        validator = Validator(validator_config)
        validator_type = validator_config.get('type') or 'per_type'

    if not path_dict.get('type'):
        if os.path.isfile(path_to_handle):
            path_dict['path'] = path_to_handle
            handle_file(path_dict, variables, verbose)
            if validate:
                validator.validate(path_dict['path'])
        else:
            lgr.error('File not found: {0}'.format(path_to_handle))
            sys.exit(codes.mapping['file_not_found'])
    else:
        if os.path.isfile(path_to_handle):
            lgr.error('If `type` is specified, `path` must not be a '
                      'path to a single file.')
            sys.exit(codes.mapping['type_path_collision'])
        if path_dict.get('to_file'):
            lgr.error('"to_file" requires explicit "path"')
            sys.exit(codes.mapping['to_file_requires_explicit_path'])
        files = get_all_files(
            path_dict['type'], path_dict['path'], path_dict['base_directory'],
            path_dict.get('excluded', []), verbose)
        lgr.info('Files found: {0}'.format(files))
        for file_to_handle in files:
            path_dict['path'] = file_to_handle
            handle_file(path_dict, variables, verbose)

            if validate and validator_type == 'per_file':
                validator.validate(path_dict['path'])

        if validate and validator_type == 'per_type':
            validator.validate(path_dict['path'])


def handle_file(path_dict, variables=None, verbose=False):
    """Handle a single file

    This will perform a validation if necessary and then
    perform the replacement in the file.

    :param dict path_dict: a dict of a single file's properties
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    if not isinstance(variables, dict):
        raise RuntimeError('Variables must be of type dict')
    lgr.debug('Vars: {0}'.format(variables))

    if not os.path.isfile(path_dict['path']):
        lgr.error('File not found: {0}'.format(path_dict['path']))
        return False

    rpx = Repex(
        path_dict['path'],
        path_dict['match'],
        path_dict['replace'],
        path_dict['with'],
        path_dict.get('to_file', False),
        verbose
    )

    validate_before = path_dict.get('validate_before', DEFAULT_VALIDATE_BEFORE)
    if not isinstance(validate_before, bool):
        lgr.error('validate_before must be of type boolean')
        sys.exit(codes.mapping['validate_before_must_be_boolean'])
    must_include = path_dict.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before and not rpx.validate_before(must_include=must_include):
        lgr.error('prevalidation failed')
        sys.exit(codes.mapping['prevalidation_failed'])

    matches = rpx.find_matches()
    rpx.replace(matches)


class Repex():
    def __init__(self, path, match, pattern, rwith,
                 to_file=False, verbose=False):
        self.path = path
        self.match = match
        self.pattern = pattern
        self.rwith = rwith
        self.to_file = to_file
        with open(self.path) as f:
            self.content = f.read()
        _set_global_verbosity_level(verbose)

    def validate_before(self, force_match=False, force_pattern=False,
                        must_include=[]):

        def verify_includes(must_include):
            """verifies that all required strings are in the file
            """
            lgr.debug('Looking for required strings: {0}'.format(
                must_include))
            # iterate over the strings and verify that
            # they exist in the file
            included = True
            for string in must_include:
                if not re.search(r'{0}'.format(string), self.content):
                    lgr.error('Required string "{0}" not found in {1}'.format(
                        string, self.path))
                    included = False
            if not included:
                return False
            lgr.debug('Required strings found.')
            return True

        def validate_pattern(force_pattern, force_match):
            """verifies that the pattern exists
            """
            lgr.debug('looking for pattern {0}'.format(self.pattern))
            # verify that the pattern you're looking to replace
            # exists in the file
            if not re.search(self.match, self.content):
                lgr.warning('match {0} not found in {1}'.format(
                    self.match, self.path))
                if force_match:
                    return False
                return True
            else:
                # find all matches of the pattern in the file
                m = self.find_matches()
                if not any(re.search(r'{0}'.format(
                        self.pattern), match) for match in m):
                    # pattern does not occur in file so we are done.
                    lgr.warning(
                        'Pattern {0} not found in any matches'.format(
                            self.pattern))
                    if force_pattern:
                        return False
                    return True
            lgr.debug('pattern found in one or more matches')
            return True

        if must_include and not verify_includes(must_include) \
                or not validate_pattern(force_pattern, force_match):
            return False
        return True

    def find_matches(self):
        """Finds all matches of an expression in a file
        """
        # compile the expression according to which we will search for matches
        expression = re.compile('(?P<matchgroup>{0})'.format(self.match))
        # look for all match groups in the content
        x = [match.groupdict() for match in expression.finditer(self.content)]
        # filter out content not in the matchgroup
        matches = [d['matchgroup'] for d in x if d.get('matchgroup')]
        lgr.debug('Matches found: {0}'.format(matches))
        return matches

    def replace(self, matches):
        """Replaces all occurences of the regex in all matches
        from a file with a specific value.
        """
        temp_file = self.path + ".tmp"
        lgr.debug('Matches to replace: {0}'.format(matches))
        output_file = self.to_file if self.to_file else self.path
        if not self.to_file:
            shutil.copy2(output_file, temp_file)
        with open(self.path) as f:
            content = f.read()
        for match in matches:
            string = re.sub(self.pattern, self.rwith, match)
            lgr.info('Replacing {0} with {1} in {2}'.format(
                match, string, self.path))
            # then replace the previous match with the newly formatted one
            content = content.replace(match, string)
        with open(temp_file, "w") as out:
            out.write(content)
        lgr.info('Writing output to {0}'.format(output_file))
        shutil.move(temp_file, output_file)


def _build_vars_dict(vars_file='', vars=None):
    repex_vars = {}
    if vars_file:
        with open(vars_file, 'r') as c:
            repex_vars = yaml.safe_load(c.read())
    if vars:
        for var in vars:
            key, value = var.split('=')
            repex_vars.update({str(key): str(value)})
    return repex_vars


class RepexError(Exception):
    pass


@click.group()
def main():
    pass


@click.command()
@click.option('-c', '--config', required=True,
              help='Path to Repex config file.')
@click.option('--vars-file', required=False,
              help='Path to YAML base vars file.')
@click.option('--var', required=False, multiple=True,
              help='A variable to pass to repex. Can be used multiple times. '
              'Format should be `\'key\'=\'value\'`.')
@click.option('-t', '--tag', required=False, multiple=True,
              help='A tag to match with a path tags. '
              'Can be used multiple times.')
@click.option('-v', '--verbose', default=False, is_flag=True)
def iter(config, vars_file, var, tag, verbose):
    """Executes Repex based on a config file.
    """
    _set_global_verbosity_level(verbose)
    logger.configure()

    repex_vars = _build_vars_dict(vars_file, var)
    iterate(config, repex_vars, verbose, list(tag))


@click.command()
@click.option('-t', '--ftype', default=None, required=False,
              help='A regex file name to look for. '
                   'Defaults to `None`, which means that '
                   '`path` must be a path to a single file.')
@click.option('-p', '--path', required=True,
              help='A regex path to look in.')
@click.option('-b', '--basedir', default=os.getcwd(), required=False,
              help='Where to start looking for `path` from. '
                   'Defaults to the cwd.')
@click.option('-m', '--match', required=False,
              help='Context match for `replace`. '
                   'If this is ommited, the context will be the '
                   'entire content of the file')
@click.option('-r', '--replace', required=True,
              help='String to replace.')
@click.option('-w', '--rwith', required=True,
              help='String to replace with.')
@click.option('-x', '--exclude', required=False, multiple=True,
              help='Paths to exclude when searching for files to handle. '
                   'This flag can be used multiple times.')
@click.option('--must-include', required=False, multiple=True,
              help='Files found must include this string. '
                   'This flag can be used multiple times.')
@click.option('--validate-before', default=False, is_flag=True,
              help='Validate that the `replace` was found in the file '
                   'before attempting to replace.')
@click.option('--validator', required=False,
              help='Validator file:function (e.g. validator.py:valid_func.')
@click.option('--validator-type', required=False, default='per_type',
              type=click.Choice(['per_file', 'per_type']),
              help='Type of validation to perform. `per_type` will validate '
                   'the last file found while `per_file` will run validation '
                   'for each file found. Defaults to `per_type`.')
@click.option('-v', '--verbose', default=False, is_flag=True)
def repl(ftype, path, basedir, match, replace, rwith, exclude, must_include,
         validate_before, validator, validator_type,
         verbose):
    """Handles replacements of files in a single path.
    """
    _set_global_verbosity_level(verbose)
    logger.configure()

    replace = r'{0}'.format(replace)
    path = r'{0}'.format(path)
    ftype = r'{0}'.format(ftype) if ftype else None
    match = r'{0}'.format(match) if match else replace

    pathobj = {
        'type': ftype,
        'path': path,
        'base_directory': basedir,
        'match': match,
        'replace': replace,
        'with': rwith,
        'excluded': list(exclude),
        'must_include': list(must_include),
        'validate_before': validate_before
    }
    if validator:
        validator_path, validator_function = validator.split(':')
        pathobj['validator'] = {
            'type': validator_type,
            'path': validator_path,
            'function': validator_function
        }

    handle_path(pathobj, verbose=verbose)

main.add_command(iter)
main.add_command(repl)
