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

repex_lgr = logger.init()
verbose_output = False


def _set_global_verbosity_level(is_verbose_output=False):
    """sets the global verbosity level for console and the repex_lgr logger.

    :param bool is_verbose_output: should be output be verbose
    """
    global verbose_output
    # TODO: (IMPRV) only raise exceptions in verbose mode
    verbose_output = is_verbose_output
    if verbose_output:
        repex_lgr.setLevel(logging.DEBUG)
    else:
        repex_lgr.setLevel(logging.INFO)
    # print 'level is: ' + str(repex_lgr.getEffectiveLevel())


def import_config(config_file):
    """returns a configuration object

    :param string config_file: path to config file
    """
    # get config file path
    repex_lgr.debug('config file is: {}'.format(config_file))
    # append to path for importing
    try:
        repex_lgr.debug('importing config...')
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        repex_lgr.error(str(ex))
        raise RuntimeError('cannot access config file')
    except yaml.parser.ParserError as ex:
        repex_lgr.error('invalid yaml file: {0}'.format(ex))
        raise RuntimeError('invalid yaml file')


def get_all_files(ftype, path, base_dir, excluded_paths=None, verbose=False):
    _set_global_verbosity_level(verbose)
    excluded_paths = excluded_paths if excluded_paths else []
    repex_lgr.debug('excluded paths: {0}'.format(excluded_paths))
    if type(excluded_paths) is not list:
        raise RepexError(
            'excluded_paths must be of type list (not {0})'.format(
                type(excluded_paths)))
    repex_lgr.info('looking for {0}\'s under {1} in {2}'.format(
        ftype, path, base_dir))
    dirs = []
    for obj in os.listdir(base_dir):
        lookup_dir = os.path.join(base_dir, obj)
        if os.path.isdir(lookup_dir) and re.search(
                r'{0}'.format(path), lookup_dir):
            if lookup_dir in excluded_paths:
                repex_lgr.info('path {0} is excluded, skipping.'.format(obj))
            else:
                dirs.append(obj)
    target_files = []
    for directory in dirs:
        for root, dirs, files in os.walk(os.path.join(base_dir, directory)):
            # append base dir to excluded paths to receive the full path
            # relative to the base_dir.
            ex_paths = [os.path.join(base_dir, e) for e in excluded_paths]
            if root in ex_paths:
                repex_lgr.info('path {0} is excluded, skipping.'.format(root))
                continue
            for f in files:
                if f == ftype and not os.path.join(root, f) in ex_paths:
                    target_files.append(os.path.join(root, f))
                elif os.path.join(root, f) in ex_paths:
                    repex_lgr.debug('path {0} is excluded, skipping.'.format(
                        os.path.join(root, f)))
    return target_files


def iterate(configfile, variables=None, verbose=False):
    """iterates over all files in `configfile`

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


def handle_path(p, variables, verbose=False):
    _set_global_verbosity_level(verbose)
    if os.path.isfile(p['path']):
        if p.get('base_directory'):
            repex_lgr.info(
                'base_directory is irrelevant when dealing with single files')
        handle_file(p, variables, verbose)
    else:
        if p.get('to_file'):
            raise RepexError(
                '"to_file" requires explicit "path"')
        files = get_all_files(
            p['type'], p['path'], p['base_directory'], p['excluded'], verbose)
        repex_lgr.info('files found: {0}'.format(files))
        for f in files:
            p['path'] = f
            handle_file(p, variables, verbose)


def handle_file(f, variables=None, verbose=False):
    """handle a single file

    this will perform a validation if necessary and then
    perform the replacement in the file.

    :param dict file: a dict of a single file's properties
    :param dict variables: a dict of variables (can be None)
    :param bool verbose: verbose output flag
    """
    _set_global_verbosity_level(verbose)
    variables = variables if variables else {}
    if type(variables) is not dict:
        raise RuntimeError('variables must be of type dict')
    p = Repex(
        f['path'],
        f['match'],
        f['replace'],
        f['with'],
        f.get('to_file', False),
        verbose
    )
    repex_lgr.debug('vars: {0}'.format(variables))
    p.expand_vars(variables)
    validate_before = f.get('validate_before', DEFAULT_VALIDATE_BEFORE)
    must_include = f.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before and not p.validate_before(must_include):
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
            repex_lgr.debug('looking for required strings: {0}'.format(
                must_include))
            # iterate over the strings and verify that
            # they exist in the file
            included = True
            for string in must_include:
                with open(self.path) as f:
                    if not any(re.search(r'{0}'.format(
                            string), line) for line in f):
                        repex_lgr.error(
                            'required string {0} not found in {1}'.format(
                                string, self.path))
                        included = False
            if not included:
                return False
            repex_lgr.debug('required strings found')
            return True

        def validate_pattern(force_pattern, force_match):
            """verifies that the pattern exists
            """
            repex_lgr.debug('looking for pattern {0}'.format(self.pattern))
            # verify that the pattern you're looking to replace
            # exists in the file
            if not re.search(self.match, self.content):
                repex_lgr.warning('match {0} not found in {1}'.format(
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
                    repex_lgr.warning(
                        'pattern {0} not found in any matches'.format(
                            self.pattern))
                    if force_pattern:
                        return False
                    return True
            repex_lgr.debug('pattern found in one or more matches')
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
        repex_lgr.debug('matches found: {0}'.format(m))
        return m

    def expand_vars(self, v):
        """expands the variables to their corresponding values
        """
        # TODO: (IMPRV) replace with dict for a more implicit
        # TODO: (IMPRV) implementation
        # TODO: (IMPRV) add expansion tests
        # iterate over all variables
        for var, value in v.items():
            # repex_lgr.debug('expanding variable: {0} to {1}'.format(
            #     var, str(v[var])))
            # replace variable in pattern
            self.pattern = self.expand_var(var, v[var], self.pattern)
            # repex_lgr.debug('pattern: {0}'.format(self.pattern))
            self.rwith = self.expand_var(var, v[var], self.rwith)
            # repex_lgr.debug('rwith: {0}'.format(self.rwith))
            self.match = self.expand_var(var, v[var], self.match)
            # repex_lgr.debug('match: {0}'.format(self.match))
            self.path = self.expand_var(var, v[var], self.path)
            # repex_lgr.debug('path: {0}'.format(self.path))

    def expand_var(self, variable, value, in_string):

        def check_if_expanded(string):
            repex_lgr.debug('verifying that string {0} expanded'.format(
                string))
            if re.search('{{ \..*}}', string):
                repex_lgr.error('string {0} failed to expand'.format(string))
                raise RepexError('string failed to expand')

        var = "{{ " + ".{0}".format(variable) + " }}"
        if re.search(var, in_string):
            repex_lgr.debug('expanding var {0} to {1} in {2}'.format(
                variable, value, in_string))
            expanded_variable = re.sub("{{ " + ".{0}".format(
                variable) + " }}", str(value), in_string)
            check_if_expanded(expanded_variable)
            return expanded_variable
        return in_string

    def replace(self, matches):
        """replaces all occurences of the regex in all matches
        from a file with a specific value.
        """
        temp_file = self.path + ".tmp"
        repex_lgr.debug('matches to replace: {0}'.format(matches))
        with open(self.path) as f:
            content = f.read()
        for m in matches:
            # replace pattern in match
            r = re.sub(self.pattern, self.rwith, m)
            repex_lgr.info('replacing {0} with {1} in {2}'.format(
                m, r, self.path))
            # then replace the previous match with the newly formatted one
            content = content.replace(m, r)
        with open(temp_file, "w") as out:
            out.write(content)
        output_file = self.to_file if self.to_file else self.path
        repex_lgr.info('writing output to {0}'.format(output_file))
        shutil.move(temp_file, output_file)


class RepexError(Exception):
    pass
