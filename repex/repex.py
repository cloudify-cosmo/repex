import logger
import logging
import os
import re
import yaml
import shutil

DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_VALIDATE_BEFORE = True
DEFAULT_VALIDATE_AFTER = False
DEFAULT_MUST_INCLUDE = []

lgr = logger.init()
verbose_output = False


def _set_global_verbosity_level(is_verbose_output=False):
    """sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    """
    global verbose_output
    # TODO: (IMPRV) only raise exceptions in verbose mode
    verbose_output = is_verbose_output
    if verbose_output:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)
    # print 'level is: ' + str(lgr.getEffectiveLevel())


def import_config(config_file):
    """returns a configuration object

    :param string config_file: path to config file
    """
    # get config file path
    lgr.debug('config file is: {}'.format(config_file))
    # append to path for importing
    try:
        lgr.info('importing config...')
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        lgr.error(str(ex))
        raise RuntimeError('cannot access config file')
    except yaml.parser.ParserError as ex:
        lgr.error('invalid yaml file: {0}'.format(ex))
        raise RuntimeError('invalid yaml file')


def get_all_files(file_name_regex, path, base_dir, excluded_paths=None,
                  verbose=False, exclude_file_name_regex=None):
    _set_global_verbosity_level(verbose)
    excluded_paths = excluded_paths if excluded_paths else []
    lgr.debug('excluded paths: {0}'.format(excluded_paths))
    if type(excluded_paths) is not list:
        raise RepexError(
            'excluded_paths must be of type list (not {0})'.format(
                type(excluded_paths)))
    lgr.info('looking for {0}\'s under {1} in {2}'.format(
        file_name_regex, path, base_dir))
    dirs = []
    for obj in os.listdir(base_dir):
        lookup_dir = os.path.join(base_dir, obj)
        if os.path.isdir(lookup_dir) and re.search(
                r'{0}'.format(path), lookup_dir):
            if lookup_dir in excluded_paths:
                lgr.info('path {0} is excluded, skipping.'.format(obj))
            else:
                dirs.append(obj)
    target_files = []
    for directory in dirs:
        for root, dirs, files in os.walk(os.path.join(base_dir, directory)):
            # append base dir to excluded paths to receive the full path
            # relative to the base_dir.
            ex_paths = [os.path.join(base_dir, e) for e in excluded_paths]
            if root in ex_paths:
                lgr.info('path {0} is excluded, skipping.'.format(root))
                continue
            for f in files:
                if re.match(
                        r'{0}'.format(file_name_regex), f)\
                        and not re.match(
                            r'{0}'.format(exclude_file_name_regex), f)\
                        and not os.path.join(root, f) in ex_paths:
                    target_files.append(os.path.join(root, f))
                elif os.path.join(root, f) in ex_paths:
                    lgr.debug('path {0} is excluded, skipping.'.format(
                        os.path.join(root, f)))
    return target_files


class VarHandler():
    """handles variable expansion and replacement
    """
    def __init__(self, verbose=False):
        _set_global_verbosity_level(verbose)

    def expand(self, vars, attributes):
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
        for var, value in vars.items():
            for attribute in attributes.keys():
                if isinstance(attributes[attribute], str):
                    attributes[attribute] = self.expand_var(
                        var, vars[var], attributes[attribute])
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
                raise RepexError('string failed to expand')

        var = "{{ " + ".{0}".format(variable) + " }}"
        if re.search(var, in_string):
            lgr.debug('expanding var {0} to {1} in {2}'.format(
                variable, value, in_string))
            expanded_variable = re.sub("{{ " + ".{0}".format(
                variable) + " }}", str(value), in_string)
            check_if_expanded(expanded_variable, variable)
            return expanded_variable
        return in_string


def iterate(configfile, variables=None, verbose=False):
    """iterates over all paths in `configfile`

    :param string configfile: yaml path with files to iterate over
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    config = import_config(configfile)
    try:
        paths = config['paths']
    except TypeError:
        raise RepexError('no paths configured')

    for path in paths:
        handle_path(path, variables, verbose)


def handle_path(p, variables=None, verbose=False):
    """iterates over all files in p['path']

    :param dict p: a dict of a specific path in the config
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    if type(variables) is not dict:
        raise RuntimeError('variables must be of type dict')
    var_expander = VarHandler(verbose)
    p = var_expander.expand(variables, p)
    p['base_directory'] = p.get('base_directory', '')
    lgr.debug('path to process: {0}'.format(
        os.path.join(p['base_directory'], p['path'])))
    path_to_handle = os.path.join(p['base_directory'], p['path'])
    if not p.get('type'):
        if os.path.isfile(path_to_handle):
            p['path'] = path_to_handle
            handle_file(p, variables, verbose)
        else:
            raise RepexError('file not found: {0}'.format(path_to_handle))
    else:
        if os.path.isfile(path_to_handle):
            raise RepexError('if `type` is specified, `path` must not be a '
                             'path to a single file.')
        if p.get('to_file'):
            raise RepexError(
                '"to_file" requires explicit "path"')
        files = get_all_files(
            p['type'], p['path'], p['base_directory'],
            p.get('excluded', []), verbose)
        lgr.info('files found: {0}'.format(files))
        for f in files:
            p['path'] = f
            handle_file(p, variables, verbose)


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
    if type(variables) is not dict:
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
        raise RepexError('validate_before must be either of type boolean')
    must_include = f.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before and not p.validate_before(must_include=must_include):
        raise RepexError('prevalidation failed')
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
