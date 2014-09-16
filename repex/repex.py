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
    # except SyntaxError:
    #     repex_lgr.error('config file syntax is malformatted. please fix '
    #                     'any syntax errors you might have and try again.')
    #     raise RuntimeError('bad config file')


def get_all_files(ftype, path, base_dir):
    repex_lgr.info('looking for {0}\'s under {1} in {2}'.format(
        ftype, path, base_dir))
    dirs = []
    for obj in os.listdir(base_dir):
        lookup_dir = os.path.join(base_dir, obj)
        # repex_lgr.info('looking for {0} in lookup dir: {1}'.format(
        #    path, lookup_dir))
        if os.path.isdir(lookup_dir) and re.search(
                r'{0}'.format(path), lookup_dir):
            dirs.append(obj)

    # dirs = [
    #     x for x in os.listdir(base_dir)
    #     if os.path.isdir(lookup_dir) and re.search(
    #         r'{0}'.format(path), lookup_dir)
    # ]
    # repex_lgr.info('dirs: {0}'.format(dirs))
    target_files = []
    for directory in dirs:
        # repex_lgr.info('iterating over {0}'.format(
        #    os.path.join(base_dir, directory)))
        for root, dirs, files in os.walk(os.path.join(base_dir, directory)):
            for f in files:
                if f == ftype:
                    # repex_lgr.info('found file:' + f)
                    target_files.append(os.path.join(root, f))
    # repex_lgr.info('files: {0}'.format(target_files))
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
        handle_path(path, variables, verbose=False)


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
        files = get_all_files(p['type'], p['path'], p['base_directory'])
        repex_lgr.info(files)
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
    validate_before = f.get('validate_before', DEFAULT_VALIDATE_BEFORE)
    must_include = f.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before and not p.validate_before(must_include):
            raise RepexError('prevalidation failed')
    matches = p.find_matches()
    p.extend_vars(variables)
    p.replace(matches)


class Repex():
    def __init__(self, path, match, pattern, rwith,
                 to_file=False, verbose=False):
        self.path = path
        self.match = match
        self.pattern = pattern
        self.rwith = rwith
        self.to_file = to_file
        _set_global_verbosity_level(verbose)

    def validate_before(self, must_include=[]):

        def verify_includes(must_include):
            """verifies that all required strings are in the file
            """
            # first, see if the pattern is even in the file.
            repex_lgr.debug('looking for required strings')
            repex_lgr.debug('must include is {0}'.format(must_include))

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
            return True

        def validate_pattern():
            """verifies that the pattern exists
            """
            repex_lgr.debug('looking for pattern to replace')
            # verify that the pattern you're looking to replace
            # exists in the file
            with open(self.path) as f:
                content = f.read()
                repex_lgr.info('file content is: {0}'.format(content))
                repex_lgr.info('file is: {0}'.format(self.path))
                if not re.search(r'{0}'.format(self.match), content):
                    repex_lgr.warning('match {0} not found in {1}'.format(
                        self.match, self.path))
                    return False
                else:
                    m = re.findall(self.match, content)
                    repex_lgr.info('matches are: {0}'.format(m))
                    if not any(re.search(r'{0}'.format(
                            self.pattern), match) for match in m):
                        # pattern does not occur in file so we are done.
                        repex_lgr.warning(
                            'pattern {0} not found in any matches'.format(
                                self.pattern))
                        return False
                    repex_lgr.debug(
                        'pattern {0} found in one or more matches'.format(
                            self.pattern))
                return True

        if must_include:
            return verify_includes(must_include)
        return validate_pattern()

    def find_matches(self):
        """finds all matches of an expression in a file
        """
        with open(self.path) as f:
            return re.findall(self.match, f.read())

    def extend_vars(self, v):
        """extends the variables to their corresponding values
        """
        # TODO: (IMPRV) replace with dict for a more implicit
        # TODO: (IMPRV) implementation
        # iterate over all variables
        for var, value in v.items():
            # replace variable in pattern
            self.pattern = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.pattern)
            # replace variable in input data
            self.rwith = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.rwith)
            self.match = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.match)
            self.path = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.path)

    def replace(self, matches):
        """replaces all occurences of the regex in all matches
        from a file with a specific value.
        """
        temp_file = self.path + ".tmp"
        repex_lgr.info('{0}: replacing {1} with {2}'.format(
            self.path, self.pattern, self.rwith))
        repex_lgr.debug('matches are: {0}'.format(matches))
        with open(self.path) as f:
            content = f.read()
        for m in matches:
            # replace pattern in match
            r = re.sub(self.pattern, self.rwith, m)
            repex_lgr.info('replacing {0} with {1}'.format(m, r))
            # then replace the previous match with the newly formatted one
            content = content.replace(m, r)
        with open(temp_file, "w") as out:
            out.write(content)
        output_file = self.to_file if self.to_file else self.path
        repex_lgr.info('writing output to {0}'.format(output_file))
        shutil.move(temp_file, output_file)


class RepexError(Exception):
    pass
