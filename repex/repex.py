import logger
import logging
import os
import re
import yaml
import sys

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


def _import_validation_methods_file(methods_file):
    # get config file path
    methods_file = methods_file or os.path.join(
        os.getcwd(), DEFAULT_CONFIG_FILE)
    repex_lgr.debug('config file is: {}'.format(methods_file))
    # append to path for importing
    sys.path.append(os.path.dirname(methods_file))
    try:
        repex_lgr.debug('importing generator dict...')
        return __import__(os.path.basename(os.path.splitext(
            methods_file)[0]))
    # TODO: (IMPRV) remove from path after importing
    except ImportError:
        repex_lgr.warning('config file not found: {}.'.format(methods_file))
        raise RepexError('missing config file')
    except SyntaxError:
        repex_lgr.error('config file syntax is malformatted. please fix '
                        'any syntax errors you might have and try again.')
        raise RepexError('bad config file')


def import_config(config_file):
    """returns a configuration object

    :param string config_file: path to config file
    """
    # get config file path
    config_file = config_file or os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE)
    repex_lgr.debug('config file is: {}'.format(config_file))
    # append to path for importing
    try:
        repex_lgr.debug('importing config...')
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        repex_lgr.error(str(ex))
        raise RuntimeError('cannot access config file')
    except ImportError:
        repex_lgr.warning('config file not found: {}.'.format(config_file))
        raise RuntimeError('missing config file')
    except SyntaxError:
        repex_lgr.error('config file syntax is malformatted. please fix '
                        'any syntax errors you might have and try again.')
        raise RuntimeError('bad config file')


def iterate(configfile=None, variables=None, verbose=False):
    """iterates over all files in `configfile`
    """
    config = import_config(configfile)
    try:
        files = config['files']
    except ValueError:
        raise RepexError('no files configured')
    for file in files:
        handle_file(file, variables, verbose)


def handle_file(file, variables, verbose=False):
    p = Repex(
        file['path'],
        file['replace'],
        file['with'],
        verbose
    )
    validate_before = file.get(
        'validate_before', DEFAULT_VALIDATE_BEFORE)
    must_include = file.get('must_include', DEFAULT_MUST_INCLUDE)
    if validate_before:
        if not p.validate_before(must_include):
            raise RuntimeError('prevalidation failed')
    p.replace(variables)


class Repex():
    def __init__(self, path, pattern, rwith, verbose=False):
        self.path = path
        self.pattern = pattern
        self.rwith = rwith
        _set_global_verbosity_level(verbose)

    def validate_before(self, must_include):

        def verify_includes(must_include):
            # first, see if the pattern is even in the file.
            repex_lgr.debug('looking for required strings')
            if must_include:
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

        def validate_pattern(pattern):
            repex_lgr.debug('looking for pattern to replace')
            # verify that the pattern you're looking to replace
            # exists in the file
            with open(self.path) as f:
                if not any(re.search(r'{0}'.format(
                        self.pattern), line) for line in f):
                    # pattern does not occur in file so we are done.
                    repex_lgr.warning('pattern {0} not found in {1}'.format(
                        self.pattern, self.path))
                    return False
                repex_lgr.debug('pattern {0} found in {1}'.format(
                    self.pattern, self.path))
                return True

        if verify_includes(must_include):
            return validate_pattern()
        return False

    def replace(self, v):
        # iterate over all variables
        for var, value in v.items():
            repex_lgr.debug('variable {0}: {1}'.format(var, value))
            # replace variable in pattern
            pattern = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.pattern)
            # replace variable in input data
            rwith = re.sub("{{ " + ".{0}".format(
                var) + " }}", str(v[var]), self.rwith)
        with open(self.path) as f:
            tmpf = self.path + ".tmp"
            with open(tmpf, "w") as out:
                repex_lgr.info('{0}: replacing {1} with {2}'.format(
                    self.path, pattern, rwith))
                for line in f:
                    # replace in the file
                    out.write(re.sub(pattern, rwith, line))
                os.rename(tmpf, self.path)


class RepexError(Exception):
    pass
