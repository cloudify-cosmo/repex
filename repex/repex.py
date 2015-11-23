import logging
import os
import re
import shutil
import sys
import imp

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
    """sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    """
    if is_verbose_output:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)


def import_config(config_file):
    """returns a configuration object

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
    excluded_paths = [os.path.join(base_dir, x).rstrip('/')
                      for x in excluded_paths]
    lgr.debug('Excluded paths: {0}'.format(excluded_paths))
    lgr.info('Looking for {0}\'s under {1} in {2}...'.format(
        file_name_regex, path, base_dir))
    if exclude_file_name_regex:
        lgr.info('Excluding all files named: {0}'.format(
            exclude_file_name_regex))
    target_files = []
    for root, _, files in os.walk(base_dir):
        # for each folder in root, check if it begins with one of excluded_path
        if not root.startswith(tuple(excluded_paths)):
            if re.search(r'{0}'.format(path), root):
                for f in files:
                    file_path = os.path.join(root, f)
                    if os.path.isfile(file_path) \
                            and re.match(r'{0}'.format(file_name_regex), f) \
                            and not re.match(r'{0}'.format(
                                exclude_file_name_regex), f):
                        if file_path not in excluded_paths:
                            lgr.debug('{0} is a match. Appending to '
                                      'list...'.format(file_path))
                            target_files.append(file_path)
                        else:
                            lgr.debug('{0} is excluded, Skipping...'.format(
                                file_path))
        else:
            lgr.debug('{0} is excluded. Skipping...'.format(root))
    lgr.info('Files to handle: {0}'.format(target_files))
    return target_files


class Validator():
    def __init__(self, validator_config):
        self.config = validator_config
        self._validate_config()

    def validate(self, path_to_validate):
        validator = self._import_validator(self.config['path'])
        lgr.info('Validating {0} using {1}...'.format(
            path_to_validate, self.config['function']))
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
    """handles variable expansion and replacement
    """
    def __init__(self, verbose=False):
        _set_global_verbosity_level(verbose)

    def expand(self, repex_vars, attributes):
        """receives a list of variables and a dict of attributes
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

        # iterate over all variables
        lgr.info('expanding variables...')
        for var, value in repex_vars.items():
            for attribute in attributes.keys():
                obj = attributes[attribute]
                if isinstance(obj, str):
                    # TODO: Handle cases where var is referenced
                    # TODO: but not defined
                    attributes[attribute] = self.expand_var(
                        var, value, obj)
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        attributes[attribute][k] = self.expand_var(
                            var, value, v)
                elif isinstance(obj, list):
                    for item in obj:
                        i = obj.index(item)
                        attributes[attribute][i] = self.expand_var(
                            var, value, item)
        return attributes

    def expand_var(self, variable, value, in_string):
        """expands variable to its corresponding value in_string

        :param string variable: variable name
        :param value: value to replace with
        :param string in_string: the string to replace in
        """
        def check_if_expanded(string, variable):
            lgr.debug('verifying that string {0} expanded'.format(
                string))
            if re.search('{{ ' + '.{0}'.format(variable) + ' }}', string):
                lgr.error('string {0} failed to expand'.format(string))
                sys.exit(codes.mapping['string_failed_to_expand'])

        var = "{{ " + ".{0}".format(variable) + " }}"
        if re.search(var, in_string):
            lgr.debug('expanding var {0} to {1} in {2}'.format(
                variable, value, in_string))
            expanded_variable = re.sub("{{ " + ".{0}".format(
                variable) + " }}", str(value), in_string)
            check_if_expanded(expanded_variable, variable)
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


def handle_path(p, variables=None, verbose=False):
    """Iterates over all files in p['path']

    :param dict p: a dict of a specific path in the config
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    var_expander = VarHandler(verbose)
    p = var_expander.expand(variables, p)
    p['base_directory'] = p.get('base_directory', '')
    lgr.debug('path to process: {0}'.format(
        os.path.join(p['base_directory'], p['path'])))
    path_to_handle = os.path.join(p['base_directory'], p['path'])

    validator = 'validator' in p
    if validator:
        validator_config = p['validator']
        v = Validator(validator_config)
        validator_type = validator_config.get('type') or 'per_type'

    if not p.get('type'):
        if os.path.isfile(path_to_handle):
            p['path'] = path_to_handle
            handle_file(p, variables, verbose)
            if validator:
                v.validate(p['path'])
        else:
            lgr.error('file not found: {0}'.format(path_to_handle))
            sys.exit(codes.mapping['file_not_found'])
    else:
        if os.path.isfile(path_to_handle):
            lgr.error('if `type` is specified, `path` must not be a '
                      'path to a single file.')
            sys.exit(codes.mapping['type_path_collision'])
        if p.get('to_file'):
            lgr.error('"to_file" requires explicit "path"')
            sys.exit(codes.mapping['to_file_requires_explicit_path'])
        files = get_all_files(
            p['type'], p['path'], p['base_directory'],
            p.get('excluded', []), verbose)
        lgr.info('files found: {0}'.format(files))
        for f in files:
            p['path'] = f
            handle_file(p, variables, verbose)
            if validator and validator_type == 'per_file':
                v.validate(p['path'])
        if validator and validator_type == 'per_type':
            v.validate(p['path'])


def handle_file(f, variables=None, verbose=False):
    """handle a single file

    this will perform a validation if necessary and then
    perform the replacement in the file.

    :param dict f: a dict of a single file's properties
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    if not isinstance(variables, dict):
        raise RuntimeError('variables must be of type dict')
    if not os.path.isfile(f['path']):
        lgr.error('file not found: {0}'.format(f['path']))
        return False
    p = Repex(
        f['path'],
        f['match'],
        f['replace'],
        f['with'],
        f.get('to_file', False),
        verbose
    )
    lgr.debug('vars: {0}'.format(variables))
    validate_before = f.get('validate_before', DEFAULT_VALIDATE_BEFORE)
    if not isinstance(validate_before, bool):
        lgr.error('validate_before must be of type boolean')
        sys.exit(codes.mapping['validate_before_must_be_boolean'])
    must_include = f.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before and not p.validate_before(must_include=must_include):
        lgr.error('prevalidation failed')
        sys.exit(codes.mapping['prevalidation_failed'])
    matches = p.find_matches()
    p.replace(matches)


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
            lgr.debug('looking for required strings: {0}'.format(
                must_include))
            # iterate over the strings and verify that
            # they exist in the file
            included = True
            for string in must_include:
                with open(self.path) as f:
                    if not any(re.search(r'{0}'.format(
                            string), line) for line in f):
                        lgr.error(
                            'required string "{0}" not found in {1}'.format(
                                string, self.path))
                        included = False
            if not included:
                return False
            lgr.debug('required strings found')
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
                        'pattern {0} not found in any matches'.format(
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
        """finds all matches of an expression in a file
        """
        r = re.compile('(?P<matchgroup>{0})'.format(
            self.match))
        x = [match.groupdict() for match in r.finditer(self.content)]
        m = [d['matchgroup'] for d in x if d.get('matchgroup')]
        lgr.debug('matches found: {0}'.format(m))
        return m

    def replace(self, matches):
        """replaces all occurences of the regex in all matches
        from a file with a specific value.
        """
        temp_file = self.path + ".tmp"
        lgr.debug('matches to replace: {0}'.format(matches))
        with open(self.path) as f:
            content = f.read()
        for m in matches:
            # replace pattern in match
            r = re.sub(self.pattern, self.rwith, m)
            lgr.info('replacing {0} with {1} in {2}'.format(
                m, r, self.path))
            # then replace the previous match with the newly formatted one
            content = content.replace(m, r)
        with open(temp_file, "w") as out:
            out.write(content)
        output_file = self.to_file if self.to_file else self.path
        lgr.info('writing output to {0}'.format(output_file))
        shutil.move(temp_file, output_file)


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
def execute(config, vars_file, var, tag, verbose):
    """Runs Repex
    """
    _set_global_verbosity_level(verbose)
    logger.configure()

    repex_vars = {}
    if vars_file:
        with open(vars_file, 'r') as c:
            repex_vars = yaml.safe_load(c.read())
    if var:
        for v in var:
            key, value = v.split('=')
            repex_vars.update({str(key): str(value)})
    iterate(config, repex_vars, verbose, list(tag))


main.add_command(execute)
