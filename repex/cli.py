# flake8: NOQA

"""Script to run Jocker via command line

Usage:
    jocker [--varsfile=<path> --templatefile=<path> --outputfile=<path> --dockerconfig=<path> --dryrun -v]
           [--build=<string>|--push=<string>]
    jocker --version

Options:
    -h --help                   Show this screen.
    -f --varsfile=<path>        Path to varsfile (if omitted, will assume "vars.py")
    -t --templatefile=<path>    Path to Dockerfile template
    -o --outputfile=<path>      Path to output Dockerfile (if omitted, will assume "Dockerfile")
    -c --dockerconfig=<path>    Path to yaml file containing docker-py configuration
    -d --dryrun                 Whether to actually generate.. or just dryrun
    -b --build=<string>         Image Repository and Tag to build
    -p --push=<string>          Image Repository and Tag to push to (will target build)
    -v --verbose                a LOT of output (Note: should be used carefully..)
    --version                   Display current version of jocker and exit
"""

from __future__ import absolute_import
from docopt import docopt
from jocker.logger import init
from jocker.jocker import _set_global_verbosity_level
from jocker.jocker import run

jocker_lgr = init()


def ver_check():
    import pkg_resources
    version = None
    try:
        version = pkg_resources.get_distribution('jocker').version
    except Exception as e:
        print(e)
    finally:
        del pkg_resources
    return version


def jocker_run(o):
    run(
        o.get('--varsfile'),
        o.get('--templatefile'),
        o.get('--outputfile'),
        o.get('--dockerconfig'),
        o.get('--dryrun'),
        o.get('--build'),
        o.get('--push'),
        o.get('--verbose')
        )


def jocker(test_options=None):
    """Main entry point for script."""
    version = ver_check()
    options = test_options or docopt(__doc__, version=version)
    _set_global_verbosity_level(options.get('--verbose'))
    jocker_lgr.debug(options)
    jocker_run(options)


def main():
    jocker()


if __name__ == '__main__':
    main()
