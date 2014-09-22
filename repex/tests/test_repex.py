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

__author__ = 'nir0s'

from repex.repex import import_config
from repex.logger import init
from repex.repex import _set_global_verbosity_level
from repex.repex import RepexError
from repex.repex import iterate
from repex.repex import Repex
from repex.repex import handle_file
from repex.repex import get_all_files

import unittest
import os
from testfixtures import log_capture
import logging


TEST_DIR = '{0}/test_dir'.format(os.path.expanduser("~"))
TEST_FILE_NAME = 'test_file'
TEST_FILE = TEST_DIR + '/' + TEST_FILE_NAME
TEST_RESOURCES_DIR = 'repex/tests/resources/'
TEST_RESOURCES_DIR_PATTERN = 'repex/tests/resource.*'
MOCK_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_files.yaml')
MOCK_CONFIG_MULTIPLE_FILES = os.path.join(TEST_RESOURCES_DIR,
                                          'mock_multiple_files.yaml')
MOCK_TEST_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_VERSION')
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_mock_files.yaml')
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_mock_files.yaml')


class TestBase(unittest.TestCase):

    @log_capture()
    def test_set_global_verbosity_level(self, capture):
        lgr = init(base_level=logging.INFO)

        _set_global_verbosity_level(is_verbose_output=False)
        lgr.debug('TEST_LOGGER_OUTPUT')
        capture.check()
        lgr.info('TEST_LOGGER_OUTPUT')
        capture.check(('user', 'INFO', 'TEST_LOGGER_OUTPUT'))

        _set_global_verbosity_level(is_verbose_output=True)
        lgr.debug('TEST_LOGGER_OUTPUT')
        capture.check(
            ('user', 'INFO', 'TEST_LOGGER_OUTPUT'),
            ('user', 'DEBUG', 'TEST_LOGGER_OUTPUT'))

    def test_import_config_file(self):
        outcome = import_config(MOCK_CONFIG_FILE)
        self.assertEquals(type(outcome), dict)
        self.assertIn('paths', outcome.keys())

    def test_fail_import_config_file(self):
        try:
            import_config('')
        except RuntimeError as ex:
            self.assertEquals(str(ex), 'cannot access config file')

    def test_import_bad_config_file_mapping(self):
        try:
            import_config(BAD_CONFIG_FILE)
        except Exception as ex:
            self.assertIn('mapping values are not allowed here', str(ex))

    def test_import_bad_config_file(self):
        try:
            import_config(BAD_CONFIG_FILE)
        except Exception as ex:
            self.assertIn('mapping values are not allowed here', str(ex))

    def test_iterate_no_config_supplied(self):
        try:
            iterate()
        except TypeError as ex:
            self.assertIn('takes at least 1 argument', str(ex))

    def test_iterate_no_files(self):
        try:
            iterate(EMPTY_CONFIG_FILE)
        except RepexError as ex:
            self.assertEqual(str(ex), 'no paths configured')

    def test_iterate(self):
        output_file = MOCK_TEST_FILE + '.test'
        v = {'version': '3.1.0-m3'}
        iterate(MOCK_CONFIG_FILE, v)
        with open(output_file) as f:
            self.assertIn('3.1.0-m3', f.read())
        os.remove(output_file)

    def test_iterate_with_vars(self):
        output_file = MOCK_TEST_FILE + '.test'
        v = {'version': '3.1.0-m3'}
        iterate(MOCK_CONFIG_FILE, v)
        with open(output_file) as f:
            self.assertIn('3.1.0-m3', f.read())
        os.remove(output_file)

    def test_iterate_variables_not_dict(self):
        try:
            iterate(MOCK_CONFIG_FILE, variables='x')
        except RuntimeError as ex:
            self.assertEqual(str(ex), 'variables must be of type dict')

    def test_file_string_not_found(self):
        p = Repex(MOCK_TEST_FILE, 'NONEXISTING STRING', '', False)
        self.assertFalse(p.validate_before(must_include=[]))

    def test_file_validation_failed(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': 'MISSING_MATCH',
            'replace': 'MISSING_PATTERN',
            'with': '',
            'to_file': MOCK_TEST_FILE + '.test',
            'validate_before': True
        }
        try:
            handle_file(file, verbose=True)
        except RepexError as ex:
            self.assertEqual(str(ex), 'prevalidation failed')

    def test_file_no_permissions_to_write_to_file(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/mock.test'
        }
        try:
            handle_file(file, verbose=True)
        except IOError as ex:
            self.assertIn('Permission denied', str(ex))

    def test_file_must_include_missing(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0',
            'with': '',
            'to_file': MOCK_TEST_FILE + '.test',
            'validate_before': True,
            'must_include': [
                'MISSING_INCLUSION'
            ]
        }
        try:
            handle_file(file, verbose=True)
        except RepexError as ex:
            self.assertEqual(str(ex), 'prevalidation failed')

    def test_iterate_multiple_files(self):
        v = {
            'preversion': '3.1.0-m2',
            'version': '3.1.0-m3'
        }
        iterate(MOCK_CONFIG_MULTIPLE_FILES, v)
        files = get_all_files(
            'mock_VERSION', TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR)
        for fl in files:
            with open(fl) as f:
                self.assertIn('3.1.0-m3', f.read())
        v['preversion'] = '3.1.0-m3'
        v['version'] = '3.1.0-m2'
        iterate(MOCK_CONFIG_MULTIPLE_FILES, v)
        for fl in files:
            with open(fl) as f:
                self.assertIn('3.1.0-m2', f.read())
