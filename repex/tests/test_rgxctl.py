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

# from jocker.jocker import JockerError
from jocker.jocker import _import_config
from jocker.jocker import init_jocker_logger
from jocker.jocker import _set_global_verbosity_level
# from jocker.jocker import Jocker
from jocker.jocker import JockerError

import unittest
import os
from testfixtures import log_capture
import logging


TEST_DIR = '{0}/test_dir'.format(os.path.expanduser("~"))
TEST_FILE_NAME = 'test_file'
TEST_FILE = TEST_DIR + '/' + TEST_FILE_NAME
TEST_RESOURCES_DIR = 'jocker/tests/resources'
MOCK_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_docker_config.py')
MOCK_TRANSPORT_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_transport.py')
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_config.py')


class TestBase(unittest.TestCase):

    @log_capture()
    def test_set_global_verbosity_level(self, capture):
        lgr = init_jocker_logger(base_level=logging.INFO)

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
        outcome = _import_config(MOCK_CONFIG_FILE)
        self.assertEquals(type(outcome), dict)
        self.assertIn('client', outcome.keys())
        self.assertIn('build', outcome.keys())

    def test_fail_import_config_file(self):
        try:
            _import_config('')
        except JockerError as ex:
            self.assertEquals(str(ex), 'missing config file')

    def test_import_bad_config_file(self):
        try:
            _import_config(BAD_CONFIG_FILE)
        except JockerError as ex:
            self.assertEquals(str(ex), 'bad config file')
