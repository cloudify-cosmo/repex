from repex import Repex
from repex import import_config
from repex import RepexError
import os

config = import_config(os.path.expanduser('tests/resources/files.yaml'))

variables = config['variables']
variables['version'] = '1.1.1.1'

try:
    files = config['files']
except ValueError:
    raise RepexError('no files configured')
for file in files:
    p = Repex(
        file['path'],
        file['replace'],
        file['with'],
    )
    validate_before = file.get(
        'validate_before', True)
    must_include = file.get('must_include', [])
    if validate_before:
        if not p.validate_before(must_include):
            raise RuntimeError('prevalidation failed')
    p.replace(variables)
    if file['validate_after']:
        p.validate_after(locals()file['validate_after'])


def validate_blueprint_yaml(yaml_file):
    return


def validate_plugins_yaml(yaml_file):
    return


def validate_types_yaml(yaml_file):
    return
