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

import repex.repex as rpx
import repex.logger as logger
import repex.codes as codes

import testtools
import os
from testfixtures import LogCapture
import logging
# import tempfile


TEST_RESOURCES_DIR = 'repex/tests/resources/'
TEST_RESOURCES_DIR_PATTERN = 'repex/tests/resource.*'
MOCK_SINGLE_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_single_file.yaml')
MOCK_MULTIPLE_FILES = os.path.join(
    TEST_RESOURCES_DIR, 'mock_multiple_files.yaml')
TEST_FILE_NAME = 'mock_VERSION'
MOCK_TEST_FILE = os.path.join(TEST_RESOURCES_DIR, 'single', TEST_FILE_NAME)
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_mock_files.yaml')
MULTIPLE_DIR = os.path.join(TEST_RESOURCES_DIR, 'multiple')
SINGLE_DIR = os.path.join(TEST_RESOURCES_DIR, 'multiple')
EXCLUDED_FILE = os.path.join(MULTIPLE_DIR, 'excluded', TEST_FILE_NAME)


class TestBase(testtools.TestCase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.version_files = []
        for root, _, files in os.walk(MULTIPLE_DIR):
            for f in files:
                if f == 'mock_VERSION':
                    self.version_files.append(os.path.join(root, f))
        self.version_files_without_excluded = \
            [f for f in self.version_files if f != EXCLUDED_FILE]
        self.excluded_files = [f for f in self.version_files if f not
                               in self.version_files_without_excluded]

    def test_set_global_verbosity_level(self):
        lgr = logger.init(base_level=logging.INFO)

        with LogCapture() as l:
            rpx._set_global_verbosity_level(is_verbose_output=False)
            lgr.debug('TEST_LOGGER_OUTPUT')
            l.check()
            lgr.info('TEST_LOGGER_OUTPUT')
            l.check(('user', 'INFO', 'TEST_LOGGER_OUTPUT'))

            rpx._set_global_verbosity_level(is_verbose_output=True)
            lgr.debug('TEST_LOGGER_OUTPUT')
            l.check(
                ('user', 'INFO', 'TEST_LOGGER_OUTPUT'),
                ('user', 'DEBUG', 'TEST_LOGGER_OUTPUT'))

    def test_iterate_no_config_supplied(self):
        ex = self.assertRaises(TypeError, rpx.iterate)
        self.assertIn('takes at least 1 argument', str(ex))

    def test_iterate_no_files(self):
        ex = self.assertRaises(
            SystemExit, rpx.iterate, EMPTY_CONFIG_FILE, {})
        self.assertEqual(codes.mapping['no_paths_configured'], ex.message)

    def test_iterate_variables_not_dict(self):
        ex = self.assertRaises(
            RuntimeError, rpx.iterate, MOCK_SINGLE_FILE, variables='x')
        self.assertEqual(str(ex), 'variables must be of type dict.')

    def test_match_not_found_in_file_force_match_and_pattern(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'NONEXISTING STRING', 'X', '')
        self.assertFalse(p.validate_before(True, True, must_include=[]))

    def test_match_not_found_in_file_no_force(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'NONEXISTING STRING', 'X', '')
        self.assertTrue(p.validate_before(False, False, must_include=[]))

    def test_match_not_found_in_file_force_match(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'NONEXISTING STRING', 'X', '')
        self.assertFalse(p.validate_before(True, False, must_include=[]))

    def test_match_not_found_in_file_force_pattern(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'NONEXISTING STRING', 'X', '')
        self.assertTrue(p.validate_before(False, True, must_include=[]))

    def test_pattern_found_in_match_force_pattern(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'version', 'ver', '')
        self.assertTrue(p.validate_before(False, True, must_include=[]))

    def test_pattern_not_found_in_match_force_pattern(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'version', 'X', '')
        self.assertFalse(p.validate_before(False, True, must_include=[]))

    def test_pattern_not_found_in_match_force_match(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'version', 'X', '')
        self.assertTrue(p.validate_before(True, False, must_include=[]))

    def test_pattern_not_found_in_match_no_force(self):
        p = rpx.Repex(MOCK_TEST_FILE, 'version', 'X', '')
        self.assertTrue(p.validate_before(False, False, must_include=[]))

    def test_file_validation_failed(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': 'MISSING_MATCH',
            'replace': 'MISSING_PATTERN',
            'with': '',
            'to_file': 'VERSION.test',
            'validate_before': True
        }
        try:
            rpx.handle_file(file, verbose=True)
        except SystemExit as ex:
            self.assertEqual(codes.mapping['prevalidation_failed'], ex.message)

    def test_file_no_permissions_to_write_to_file(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/mock.test'
        }
        try:
            rpx.handle_file(file, verbose=True)
        except IOError as ex:
            self.assertIn('Permission denied', str(ex))

    def test_file_must_include_missing(self):
        file = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0',
            'with': '',
            'to_file': 'VERSION.test',
            'validate_before': True,
            'must_include': [
                'MISSING_INCLUSION'
            ]
        }
        try:
            rpx.handle_file(file, verbose=True)
        except SystemExit as ex:
            self.assertEqual(ex.message, codes.mapping['prevalidation_failed'])

    def test_path_with_and_without_base_directory(self):
        p = {
            'path': os.path.join('single', TEST_FILE_NAME),
            'base_directory': TEST_RESOURCES_DIR,
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'validate_before': True
        }
        t = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m3',
            'replace': '3.1.0-m3',
            'with': '3.1.0-m2',
            'validate_before': True
        }
        rpx.handle_path(p, verbose=True)
        with open(p['path']) as f:
            content = f.read()
        self.assertIn('3.1.0-m3', content)
        rpx.handle_path(t, verbose=True)
        with open(t['path']) as f:
            content = f.read()
        self.assertIn('3.1.0-m2', content)

    def test_to_file_requires_explicit_path(self):
        p = {
            'type': 'x',
            'path': TEST_RESOURCES_DIR_PATTERN,
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/x.x',
            'validate_before': True
        }
        ex = self.assertRaises(
            SystemExit, rpx.handle_path, p, verbose=True)
        self.assertEquals(
            codes.mapping['to_file_requires_explicit_path'], ex.message)

    def test_file_does_not_exist(self):
        file = {
            'path': 'MISSING_FILE',
            'match': '3.1.0-m2',
            'replace': '3.1.0',
            'with': '',
            'validate_before': True
        }
        result = rpx.handle_file(file, verbose=True)
        self.assertFalse(result)

    def test_iterate_multiple_files(self):
        v = {
            'preversion': '3.1.0-m2',
            'version': '3.1.0-m3'
        }
        # iterate once
        rpx.iterate(MOCK_MULTIPLE_FILES, v, True)
        # verify that all files were modified
        for version_file in self.version_files_without_excluded:
            with open(version_file) as f:
                self.assertIn('3.1.0-m3', f.read())
        # # all other than the excluded ones
        for version_file in self.excluded_files:
            with open(version_file) as f:
                self.assertIn('3.1.0-m2', f.read())
        v['preversion'] = '3.1.0-m3'
        v['version'] = '3.1.0-m2'
        rpx.iterate(MOCK_MULTIPLE_FILES, v)
        # verify that all files were modified
        for version_file in self.version_files_without_excluded:
            with open(version_file) as f:
                self.assertIn('3.1.0-m2', f.read())
        # # all other than the excluded ones
        for version_file in self.excluded_files:
            with open(version_file) as f:
                self.assertIn('3.1.0-m2', f.read())

    def test_type_with_path_config(self):
        p = {
            'type': 'x',
            'path': MOCK_TEST_FILE,
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/x.x',
            'validate_before': True
        }
        ex = self.assertRaises(
            SystemExit, rpx.handle_path, p, verbose=True)
        self.assertEqual(codes.mapping['type_path_collision'], ex.message)

    def test_single_file_not_found(self):
        p = {
            'path': 'x',
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'validate_before': True
        }
        ex = self.assertRaises(
            SystemExit, rpx.handle_path, p, verbose=True)
        self.assertEqual(codes.mapping['file_not_found'], ex.message)


class TestConfig(testtools.TestCase):

    def test_import_config_file(self):
        outcome = rpx.import_config(MOCK_SINGLE_FILE)
        self.assertEquals(type(outcome), dict)
        self.assertIn('paths', outcome.keys())

    def test_fail_import_config_file(self):
        ex = self.assertRaises(SystemExit, rpx.import_config, '')
        self.assertEquals(
            ex.message, codes.mapping['cannot_access_config_file'])

    def test_import_bad_config_file_mapping(self):
        ex = self.assertRaises(
            SystemExit, rpx.import_config,
            os.path.join(TEST_RESOURCES_DIR, 'bad_mock_files.yaml'))
        self.assertEqual(codes.mapping['invalid_yaml_file'], ex.message)


class TestValidator(testtools.TestCase):

    def setUp(self):
        super(TestValidator, self).setUp()
        self.single_file_config = rpx.import_config(MOCK_SINGLE_FILE)
        self.single_file_output_file = \
            self.single_file_config['paths'][0]['to_file']

    def test_validator(self):
        v = {'version': '3.1.0-m3'}
        try:
            ex = self.assertRaises(
                SystemExit, rpx.iterate,
                os.path.join(
                    TEST_RESOURCES_DIR,
                    'mock_files_with_failed_validator.yaml'), v)
            self.assertEqual(codes.mapping['validator_failed'], ex.message)
            with open(self.single_file_output_file) as f:
                self.assertIn('3.1.0-m3', f.read())
        finally:
            os.remove(self.single_file_output_file)


class TestSingleFile(testtools.TestCase):

    def setUp(self):
        super(TestSingleFile, self).setUp()
        self.single_file_config = rpx.import_config(MOCK_SINGLE_FILE)
        self.single_file_output_file = \
            self.single_file_config['paths'][0]['to_file']
        self.multi_file_config = rpx.import_config(MOCK_MULTIPLE_FILES)
        self.multi_file_excluded_dirs = \
            self.multi_file_config['paths'][0]['excluded']

    def tearDown(self):
        super(TestSingleFile, self).tearDown()
        if os.path.isfile(self.single_file_output_file):
            os.remove(self.single_file_output_file)

    def test_iterate(self):
        v = {'version': '3.1.0-m3'}
        rpx.iterate(MOCK_SINGLE_FILE, v)
        with open(self.single_file_output_file) as f:
            self.assertIn('3.1.0-m3', f.read())

    def test_iterate_user_tags_no_path_tags(self):
        tags = ['test_tag']
        v = {'version': '3.1.0-m3'}
        rpx.iterate(MOCK_SINGLE_FILE, v, verbose=True, tags=tags)
        self.assertFalse(os.path.isfile(self.single_file_output_file))

    def test_iterate_path_tags_no_user_tags(self):
        tags = ['test_tag']
        self.single_file_config['paths'][0]['tags'] = tags
        v = {'version': '3.1.0-m3'}
        rpx.iterate(self.single_file_config, v, verbose=True)
        self.assertFalse(os.path.isfile(self.single_file_output_file))

    def test_iterate_path_tags_user_tags(self):
        tags = ['test_tag']
        self.single_file_config['paths'][0]['tags'] = tags
        v = {'version': '3.1.0-m3'}
        rpx.iterate(
            self.single_file_config,
            v, verbose=True, tags=tags)
        with open(self.single_file_output_file) as f:
            self.assertIn('3.1.0-m3', f.read())

    def test_iterate_any_tag(self):
        tags = ['test_tag']
        any_tag = ['any']
        self.single_file_config['paths'][0]['tags'] = tags
        v = {'version': '3.1.0-m3'}
        rpx.iterate(
            self.single_file_config,
            v, verbose=True, tags=any_tag)
        with open(self.single_file_output_file) as f:
            self.assertIn('3.1.0-m3', f.read())

    def test_iterate_with_vars(self):
        v = {'version': '3.1.0-m3'}
        rpx.iterate(MOCK_SINGLE_FILE, v)
        with open(self.single_file_output_file) as f:
            self.assertIn('3.1.0-m3', f.read())

    def test_iterate_with_vars_in_config(self):
        rpx.iterate(MOCK_SINGLE_FILE)
        with open(self.single_file_output_file) as f:
            self.assertIn('3.1.0-m4', f.read())

    def test_env_var_based_replacement(self):
        v = {'version': '3.1.0-m3'}
        os.environ['REPEX_VAR_VERSION'] = '3.1.0-m9'
        try:
            rpx.iterate(MOCK_SINGLE_FILE, v)
            with open(self.single_file_output_file) as f:
                self.assertIn('3.1.0-m9', f.read())
        finally:
            os.environ.pop('REPEX_VAR_VERSION')


class TestGetAllFiles(testtools.TestCase):

    def setUp(self):
        super(TestGetAllFiles, self).setUp()
        self.multi_file_config = rpx.import_config(MOCK_MULTIPLE_FILES)
        self.multi_file_excluded_dirs = \
            self.multi_file_config['paths'][0]['excluded']
        self.excluded_files = [os.path.join(
            self.multi_file_excluded_dirs[0], TEST_FILE_NAME)]
        self.base_dir = self.multi_file_config['paths'][0]['base_directory']

        self.version_files = []
        for root, _, files in os.walk(MULTIPLE_DIR):
            for f in files:
                if f == 'mock_VERSION':
                    self.version_files.append(os.path.join(root, f))
        self.version_files_without_excluded = \
            [f for f in self.version_files if f != EXCLUDED_FILE]
        self.excluded_files = [f for f in self.version_files if f not
                               in self.version_files_without_excluded]

    def test_get_all_files_no_exclusion(self):
        files = rpx.get_all_files(
            TEST_FILE_NAME, TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR)
        for version_file in self.version_files:
            self.assertIn(version_file, files)

    def test_get_all_files_with_file_exclusion(self):
        files = rpx.get_all_files(
            TEST_FILE_NAME, TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR,
            self.multi_file_excluded_dirs, verbose=True)
        for version_file in self.version_files_without_excluded:
            self.assertIn(version_file, files)
        for f in self.excluded_files:
            self.assertNotIn(os.path.join(self.base_dir, f), files)

    def test_get_all_files_with_dir_exclusion(self):
        files = rpx.get_all_files(
            TEST_FILE_NAME, TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR,
            self.multi_file_excluded_dirs)
        for version_file in self.version_files_without_excluded:
            self.assertIn(version_file, files)
        for f in self.excluded_files:
            self.assertNotIn(os.path.join(self.base_dir, f), files)

    def test_get_all_files_excluded_list_is_str(self):
        ex = self.assertRaises(
            SystemExit, rpx.get_all_files,
            TEST_FILE_NAME, TEST_RESOURCES_DIR_PATTERN,
            TEST_RESOURCES_DIR, 'INVALID_EXCLUDED_LIST')
        self.assertEqual(
            codes.mapping['excluded_paths_must_be_a_list'], ex.message)

    def test_get_all_regex_files(self):
        mock_yaml_files = [f for f in os.listdir(TEST_RESOURCES_DIR)
                           if (f.startswith('mock') and f.endswith('yaml'))]
        files = rpx.get_all_files(
            'mock.*\.yaml', TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR)
        self.assertEquals(len(mock_yaml_files), len(files))
        for f in mock_yaml_files:
            self.assertIn(os.path.join(TEST_RESOURCES_DIR, f), files)

    def test_get_all_regex_files_with_exclusion(self):
        mock_yaml_files = [os.path.join('single', 'mock_VERSION')]
        files = rpx.get_all_files(
            'mock.*', TEST_RESOURCES_DIR_PATTERN, TEST_RESOURCES_DIR,
            ['multiple'], True, '.*yaml',)
        self.assertEquals(len(mock_yaml_files), len(files))
        for f in mock_yaml_files:
            self.assertIn(os.path.join(TEST_RESOURCES_DIR, f), files)
