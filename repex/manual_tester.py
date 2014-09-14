from repex import import_config
from repex import RepexError
from repex import handle_file
import os
from dsl_parser.parser import parse_from_path
from dsl_parser.parser import DSLParsingException


def validate_blueprintyaml(blueprint_path):
    try:
        parse_from_path(blueprint_path)
    except DSLParsingException as ex:
        raise Exception('validation failed: {0}'.format(str(ex)))


if __name__ == "__main__":
    config = import_config(os.path.expanduser('tests/resources/files.yaml'))

    variables = config['variables']
    variables['version'] = '3.1'

    try:
        files = config['files']
    except ValueError:
        raise RepexError('no files configured')
    for file in files:
        handle_file(file, variables, verbose=True)

        if file['type'] == 'blueprint.yaml':
            validate_blueprintyaml(file['path'])
