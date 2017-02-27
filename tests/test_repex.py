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

import os
import shlex
import shutil
import tempfile

import pytest
import click.testing as clicktest

import repex


TEST_RESOURCES_DIR = os.path.join('tests', 'resources')
TEST_RESOURCES_DIR_PATTERN = os.path.join('tests', 'resource.*')
MOCK_SINGLE_FILE = os.path.join(TEST_RESOURCES_DIR, 'mock_single_file.yaml')
MOCK_MULTIPLE_FILES = os.path.join(
    TEST_RESOURCES_DIR, 'mock_multiple_files.yaml')
TEST_FILE_NAME = 'mock_VERSION'
MOCK_TEST_FILE = os.path.join(TEST_RESOURCES_DIR, 'single', TEST_FILE_NAME)
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_mock_files.yaml')
MULTIPLE_DIR = os.path.join(TEST_RESOURCES_DIR, 'multiple')
SINGLE_DIR = os.path.join(TEST_RESOURCES_DIR, 'multiple')
EXCLUDED_FILE = os.path.join(MULTIPLE_DIR, 'excluded', TEST_FILE_NAME)
MOCK_FILES_WITH_VALIDATOR = os.path.join(
    TEST_RESOURCES_DIR, 'files_with_failed_validator.yaml')


repex.set_verbose()


def _invoke(params=None):
    rpx = clicktest.CliRunner()

    if params:
        params = params if isinstance(params, list) \
            else shlex.split(params)
    return rpx.invoke(getattr(repex, 'main'), params)


class TestBase():
    def test_invoke_main(self):
        result = _invoke()
        assert 'Must either provide a path or a' in result.output

    def test_no_matches(self):
        fd, temp_file = tempfile.mkstemp()
        os.close(fd)
        result = _invoke([temp_file, '-r', 'something', '-w', 'somethingelse'])
        assert result.exit_code == 0


class TestDiff():
    def setup_method(self, test_method):
        self.original_repex_diff_home = repex._DIFF_FILE_PATH
        repex._DIFF_HOME = tempfile.mkdtemp()
        repex._DIFF_FILE_PATH = os.path.join(repex._DIFF_HOME, 'rpx-diff')
        self.diff_dir = os.path.dirname(repex._DIFF_FILE_PATH)
        shutil.rmtree(self.diff_dir, ignore_errors=True)

    def teardown_method(self, test_method):
        repex._DIFF_FILE_PATH = self.original_repex_diff_home
        shutil.rmtree(self.diff_dir, ignore_errors=True)

    def _test(self):
        with open(repex._DIFF_FILE_PATH) as diff_file:
            diff_content = diff_file.read()
        assert '6  -  "version": "3.1.0-m2",' in diff_content
        assert '7  +  "version": "3.1.0-m3",' in diff_content

    @pytest.mark.skipif(os.name == 'nt', reason='Irrelevant on Windows')
    # TODO: Fix for Windows. Fails on file not found
    def test_iterate(self):
        try:
            _invoke("-c {0} --diff --var version=3.1.0-m3".format(
                MOCK_MULTIPLE_FILES))
            self._test()
        finally:
            _invoke("-c {0} --var version=3.1.0-m2".format(
                MOCK_MULTIPLE_FILES))

    def test_single_file(self):
        variables = {'version': '3.1.0-m3'}

        try:
            repex.iterate(
                config_file_path=MOCK_SINGLE_FILE,
                variables=variables,
                with_diff=True)
            self._test()
        finally:
            variables = {'version': '3.1.0-m2'}
            repex.iterate(
                config_file_path=MOCK_SINGLE_FILE,
                variables=variables)

    def test_no_changes(self):
        variables = {'version': '3.1.0-m2'}
        repex.iterate(
            config_file_path=MOCK_SINGLE_FILE,
            variables=variables,
            with_diff=True)
        assert not os.path.exists(self.diff_dir)


class TestIterate():
    def setup_method(self, test_method):
        self.version_files = []
        for root, _, files in os.walk(MULTIPLE_DIR):
            self.version_files = \
                [os.path.join(root, f) for f in files if f == 'mock_VERSION']
        self.version_files_without_excluded = \
            [f for f in self.version_files if f != EXCLUDED_FILE]
        self.excluded_files = [f for f in self.version_files if f not
                               in self.version_files_without_excluded]

    def test_iterate_multiple_files(self):
        # Note that this also tests expanding variables in variables
        # as the variable declared in the `mock_multiple_files.yaml`
        # is being expanded itself and then used.

        def _test(replaced_value, initial_value):
            for version_file in self.version_files_without_excluded:
                with open(version_file) as f:
                    assert replaced_value in f.read()
            for version_file in self.excluded_files:
                with open(version_file) as f:
                    assert initial_value in f.read()

        # TODO: This is some stupid thing related to formatting on windows
        # The direct invocation with click doesn't work on windows..
        # probably due to some string formatting of the command.
        if os.name == 'nt':
            variables = {'preversion': '3.1.0-m2', 'version': '3.1.0-m3'}
            repex.iterate(MOCK_MULTIPLE_FILES, variables=variables)
        else:
            fd, tmp = tempfile.mkstemp()
            os.close(fd)
            with open(tmp, 'w') as f:
                f.write("version: '3.1.0-m3'")
            try:
                _invoke(
                    "-c {0} --vars-file={1} "
                    "--var='preversion'='3.1.0-m2'".format(
                        MOCK_MULTIPLE_FILES, tmp))
            finally:
                os.remove(tmp)

        _test('"version": "3.1.0-m3"', '"version": "3.1.0-m2"')
        variables = {'preversion': '3.1.0-m3', 'version': '3.1.0-m2'}
        repex.iterate(MOCK_MULTIPLE_FILES, variables=variables)
        _test('"version": "3.1.0-m2"', '"version": "3.1.0-m2"')

    @pytest.mark.skipif(os.name == 'nt', reason='Irrelevant on Windows')
    def test_iterate_validate_only(self):
        result = _invoke("-c {0} --validate-only".format(MOCK_MULTIPLE_FILES))
        # This is enough for now. If the validation succeeded, we would expect
        # it to raise an exception, which happens in other
        assert result.exit_code == 0

    @pytest.mark.skipif(os.name == 'nt', reason='Irrelevant on Windows')
    def test_iterate_validate_only_no_validate(self):
        result = _invoke("-c {0} --validate-only --no-validate".format(
            MOCK_MULTIPLE_FILES))
        # This is enough for now. If the validation succeeded, we would expect
        # it to raise an exception, which happens in other
        assert result.exit_code == 2
        assert '`validate_only` is mutually exclusive' in result.output

    def test_replace_multiple_files(self):

        def _test(path, params, initial_value, final_value):
            result = _invoke([path] + params)
            assert result.exit_code == 1
            # verify that all files were modified
            for version_file in self.version_files_without_excluded:
                with open(version_file) as f:
                    assert initial_value in f.read()
            # all other than the excluded ones
            for version_file in self.excluded_files:
                with open(version_file) as f:
                    assert final_value in f.read()

        params = [
            '-t', 'mock_VERSION',
            '-b', 'tests/resources/',
            '-x', 'multiple/exclude',
            '-m', '"version": "\d+\.\d+(\.\d+)?(-\w\d+)?"',
            '-r', '\d+\.\d+(\.\d+)?(-\w\d+)?',
            '-w', '3.1.0-m3',
            '--must-include=date',
            '--validator=tests/resources/validator.py:validate',
        ]
        _test('multiple', params, '3.1.0-m3', '3.1.0-m2')
        params[11] = '3.1.0-m2'
        _test('multiple', params, '3.1.0-m2', '3.1.0-m2')
        params[9] = 'NON_EXISTING_STRING'
        _test('multiple', params, '3.1.0-m2', '3.1.0-m2')

    def test_illegal_iterate_invocation(self):
        result = _invoke('-c non_existing_config -v')
        assert type(result.exception) == SystemExit
        assert result.exit_code == 1
        assert 'Could not open config file: ' in result.output

    def test_illegal_replace_invocation(self):
        result = _invoke('non_existing_path -r x -w y')
        assert type(result.exception) == SystemExit
        assert result.exit_code == 1
        assert 'File not found: ' in result.output

    def test_mutually_exclusive_arguments(self):
        result = _invoke('--ftype=non_existing_path --to-file=x')
        assert type(result.exception) == SystemExit
        assert 'is mutually exclusive with' in result.output

    def test_iterate_no_config_supplied(self):
        with pytest.raises(repex.RepexError) as ex:
            repex.iterate()
        assert repex.ERRORS['no_config_supplied'] in str(ex)

    def test_iterate_no_files(self):
        with pytest.raises(repex.RepexError) as ex:
            repex.iterate(config_file_path=EMPTY_CONFIG_FILE, variables={})
        assert "'paths' is a required property" in str(ex)

    def test_iterate_variables_not_dict(self):
        with pytest.raises(TypeError) as ex:
            repex.iterate(config_file_path=MOCK_SINGLE_FILE, variables='x')
        assert repex.ERRORS['variables_not_dict'] in str(ex)


class TestPathHandler():
    @pytest.mark.skipif(os.name == 'nt', reason='Irrelevant on Windows')
    def test_file_no_permissions_to_write_to_file(self):
        path_object = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/mock.test'
        }
        with pytest.raises(IOError) as ex:
            repex.handle_path(path_object)
        assert 'Permission denied' in str(ex)

    def _test_repex_errors(self,
                           path_object,
                           error,
                           error_type=repex.RepexError):
        with pytest.raises(error_type) as ex:
            repex.handle_path(path_object)
        assert repex.ERRORS[error] in str(ex)

    def test_file_must_include_missing(self):
        path_object = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m2',
            'replace': '3.1.0',
            'with': '',
            'to_file': 'VERSION.test',
            'must_include': [
                'MISSING_INCLUSION'
            ]
        }
        expected_error = 'prevalidation_failed'
        self._test_repex_errors(path_object, expected_error)

    def _test_path_with_and_without_base_directory(self):
        p = {
            'path': os.path.join('single', TEST_FILE_NAME),
            'base_directory': TEST_RESOURCES_DIR,
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
        }
        t = {
            'path': MOCK_TEST_FILE,
            'match': '3.1.0-m3',
            'replace': '3.1.0-m3',
            'with': '3.1.0-m2',
        }
        repex.handle_path(p)
        with open(p['path']) as f:
            content = f.read()
        assert '3.1.0-m2' not in content
        assert '3.1.0-m3' in content
        repex.handle_path(t)
        with open(t['path']) as f:
            content = f.read()
        assert '3.1.0-m2' in content
        assert '3.1.0-m3' not in content

    def test_to_file_requires_explicit_path(self):
        path_object = {
            'type': 'x',
            'path': TEST_RESOURCES_DIR_PATTERN,
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/x.x',
        }
        expected_error = 'to_file_requires_explicit_path'
        self._test_repex_errors(path_object, expected_error)

    def test_file_does_not_exist(self):
        path_object = {
            'path': 'MISSING_FILE',
            'match': '3.1.0-m2',
            'replace': '3.1.0',
            'with': '',
        }
        expected_error = 'file_not_found'
        self._test_repex_errors(path_object, expected_error)

    def test_type_with_path_config(self):
        path_object = {
            'type': 'x',
            'path': MOCK_TEST_FILE,
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3',
            'to_file': '/x.x',
        }
        expected_error = 'type_path_collision'
        self._test_repex_errors(path_object, expected_error)

    def test_single_file_not_found(self):
        path_object = {
            'path': 'x',
            'base_directory': '',
            'match': '3.1.0-m2',
            'replace': '3.1.0-m2',
            'with': '3.1.0-m3'
        }
        expected_error = 'file_not_found'
        self._test_repex_errors(path_object, expected_error)


class TestConfig():

    def test_import_config_file(self):
        config = repex._get_config(config_file_path=MOCK_SINGLE_FILE)
        assert type(config['paths']) == list
        assert type(config['variables']) == dict

    def test_config_file_not_found(self):
        with pytest.raises(repex.RepexError) as ex:
            repex._get_config(config_file_path='non_existing_path')
        assert repex.ERRORS['config_file_not_found'] in str(ex)

    def test_import_bad_config_file_mapping(self):
        with pytest.raises(repex.RepexError) as ex:
            repex._get_config(config_file_path=os.path.join(
                TEST_RESOURCES_DIR, 'bad_mock_files.yaml'))
        assert repex.ERRORS['invalid_yaml'] in str(ex)


class TestValidator():

    def setup_method(self, test_method):
        self.single_file_config = repex._get_config(MOCK_SINGLE_FILE)
        self.with_validator_config = repex._get_config(
            MOCK_FILES_WITH_VALIDATOR)
        self.single_file_output_file = \
            self.single_file_config['paths'][0]['to_file']
        self.validator_config = \
            self.with_validator_config['paths'][0]['validator']

    def test_validator(self):
        variables = {'version': '3.1.0-m3'}

        try:
            repex.iterate(
                config=self.with_validator_config,
                variables=variables)
        finally:
            os.remove(self.single_file_output_file)

    def test_failed_validator_per_file(self):
        variables = {'version': '3.1.0-m3'}

        self.with_validator_config['paths'][0]['validator']['function'] = \
            'fail_validate'

        try:
            with pytest.raises(repex.RepexError) as ex:
                repex.iterate(
                    config=self.with_validator_config,
                    variables=variables)
            assert repex.ERRORS['validation_failed'] in str(ex)

            with open(self.single_file_output_file) as f:
                assert '3.1.0-m3' in f.read()
        finally:
            os.remove(self.single_file_output_file)

    def _check_config(self, error):
        with pytest.raises(repex.RepexError) as ex:
            repex._Validator(self.validator_config)
        assert repex.ERRORS[error] in str(ex)

    def test_invalid_validator_type(self):
        self.validator_config.update({'type': 'bad_type'})
        with pytest.raises(repex.RepexError) as ex:
            repex.iterate(config=self.with_validator_config)
        assert "bad_type' is not one of ['per_type', 'per_file']" in str(ex)

    def test_validator_path_not_found(self):
        self.validator_config.update({'path': 'bad_path'})
        self._check_config('validator_path_not_found')

    def test_validator_function_not_found(self):
        self.validator_config.update({'function': 'bad_function'})
        self.validator_config['path'] = os.path.join(
            TEST_RESOURCES_DIR, 'validator.py')
        validator = repex._Validator(self.validator_config)
        with pytest.raises(repex.RepexError) as ex:
            validator.validate('some_file')
        assert repex.ERRORS['validator_function_not_found'] in str(ex)


class TestTags():
    def test_match_any_empty(self):
        repex_tags = ['any']
        path_tags = []
        assert repex._match_tags(repex_tags, path_tags)

    def test_match_any_with_tag(self):
        repex_tags = ['any']
        path_tags = ['just_a_tag']
        assert repex._match_tags(repex_tags, path_tags)

    def test_match(self):
        repex_tags = ['just_a_tag']
        path_tags = ['just_a_tag']
        assert repex._match_tags(repex_tags, path_tags)

    def test_match_one_of(self):
        repex_tags = ['just_a_tag', 'other_tag']
        path_tags = ['just_a_tag', 'other_other_tag']
        assert repex._match_tags(repex_tags, path_tags)

    def test_match_no_tags_chosen(self):
        repex_tags = []
        path_tags = []
        assert repex._match_tags(repex_tags, path_tags)

    def test_no_match(self):
        repex_tags = ['not_a_tag']
        path_tags = ['just_a_tag']
        assert not repex._match_tags(repex_tags, path_tags)

    def test_no_match_path_has_tags_but_none_chosen(self):
        repex_tags = []
        path_tags = ['some_tag']
        assert not repex._match_tags(repex_tags, path_tags)

    def test_no_match_tags_chosen_but_path_has_no_tags(self):
        repex_tags = ['some_tag']
        path_tags = []
        assert not repex._match_tags(repex_tags, path_tags)


class TestSingleFile():

    def setup_method(self, test_method):
        self.single_file_config = repex._get_config(MOCK_SINGLE_FILE)
        self.single_file_output_file = \
            self.single_file_config['paths'][0]['to_file']
        self.multi_file_config = repex._get_config(MOCK_MULTIPLE_FILES)
        self.multi_file_excluded_dirs = \
            self.multi_file_config['paths'][0]['excluded']

    def teardown_method(self, test_method):
        if os.path.isfile(self.single_file_output_file):
            os.remove(self.single_file_output_file)

    def test_iterate(self):
        variables = {'version': '3.1.0-m3'}
        repex.iterate(
            config_file_path=MOCK_SINGLE_FILE,
            variables=variables)
        with open(self.single_file_output_file) as f:
            assert '3.1.0-m3' in f.read()

    def test_iterate_user_tags_no_path_tags(self):
        tags = ['test_tag']
        variables = {'version': '3.1.0-m3'}
        repex.iterate(
            config_file_path=MOCK_SINGLE_FILE,
            variables=variables,
            tags=tags)
        assert not os.path.isfile(self.single_file_output_file)

    def test_iterate_path_tags_no_user_tags(self):
        tags = ['test_tag']
        self.single_file_config['paths'][0]['tags'] = tags
        variables = {'version': '3.1.0-m3'}
        repex.iterate(config=self.single_file_config, variables=variables)
        assert not os.path.isfile(self.single_file_output_file)

    def test_iterate_path_tags_user_tags(self):
        tags = ['test_tag']
        self.single_file_config['paths'][0]['tags'] = tags
        variables = {'version': '3.1.0-m3'}
        repex.iterate(
            config=self.single_file_config,
            variables=variables,
            tags=tags)
        with open(self.single_file_output_file) as f:
            assert '3.1.0-m3' in f.read()

    def test_iterate_any_tag(self):
        tags = ['test_tag']
        any_tag = ['any']
        self.single_file_config['paths'][0]['tags'] = tags
        variables = {'version': '3.1.0-m3'}
        repex.iterate(
            config=self.single_file_config,
            variables=variables,
            tags=any_tag)
        with open(self.single_file_output_file) as f:
            assert '3.1.0-m3' in f.read()

    def test_tags_not_list(self):
        tags = 'x'
        with pytest.raises(TypeError) as ex:
            repex.iterate(config=self.single_file_config, tags=tags)
        assert repex.ERRORS['tags_not_list'] in str(ex)

    def test_iterate_with_vars(self):
        variables = {'version': '3.1.0-m3'}
        repex.iterate(
            config_file_path=MOCK_SINGLE_FILE,
            variables=variables)
        with open(self.single_file_output_file) as f:
            assert '3.1.0-m3' in f.read()

    def test_iterate_with_vars_in_config(self):
        repex.iterate(config_file_path=MOCK_SINGLE_FILE)
        with open(self.single_file_output_file) as f:
            assert '3.1.0-m4' in f.read()

    def test_env_var_based_replacement(self):
        variables = {'version': '3.1.0-m3'}
        os.environ['REPEX_VAR_VERSION'] = '3.1.0-m9'
        try:
            repex.iterate(
                config_file_path=MOCK_SINGLE_FILE,
                variables=variables)
            with open(self.single_file_output_file) as f:
                assert '3.1.0-m9' in f.read()
        finally:
            os.environ.pop('REPEX_VAR_VERSION')


class TestVariableExpansion():
    def test_replace_using_infile_vars(self):
        pass

    def test_replace_using_api_vars(self):
        pass

    def test_replace_using_env_vars(self):
        pass

    def test_expand_variables_in_string(self):
        attributes = {'path': '{{ .some_var }}'}
        variables = {'some_var': '3.1.0-m3'}

        variable_expander = repex._VariablesHandler()
        attributes = variable_expander.expand(variables, attributes)
        assert attributes['path'] == '3.1.0-m3'

    def test_expand_variables_in_dict(self):
        attributes = {
            'validator': {
                'type': 'per_file',
                'path': '/{{ .path }}',
                'function': 'validate'
            }
        }
        variables = {'path': 'my_validator.py'}

        variable_expander = repex._VariablesHandler()
        attributes = variable_expander.expand(variables, attributes)
        assert attributes['validator']['path'] == '/my_validator.py'

    def test_expand_variables_in_list(self):
        attributes = {'must_include': ['x', 'y', '{{ .my_string }}']}
        variables = {'my_string': 'my_value'}

        variable_expander = repex._VariablesHandler()
        attributes = variable_expander.expand(variables, attributes)
        assert attributes['must_include'][2] == 'my_value'

    def test_expand_variables_on_same_attribute(self):
        attributes = {'path': '{{ .some_var }}-{{ .some_other_var }}'}
        variables = {'some_var': '3.1.0', 'some_other_var': 'm3'}

        variable_expander = repex._VariablesHandler()
        attributes = variable_expander.expand(variables, attributes)
        assert attributes['path'] == '3.1.0-m3'

    def test_variable_not_expanded(self):
        attributes = {'path': '"{{ .some_var }}"'}
        variables = {'some_other_var': '3.1.0-m3'}

        variable_expander = repex._VariablesHandler()
        with pytest.raises(repex.RepexError) as ex:
            variable_expander.expand(variables, attributes)
        assert "Variables failed to expand: ['{{ .some_var }}']" in str(ex)


class TestGetAllFiles():

    def setup_method(self, test_method):
        self.multi_file_config = repex._get_config(MOCK_MULTIPLE_FILES)
        self.multi_file_excluded_dirs = \
            self.multi_file_config['paths'][0]['excluded']
        self.excluded_files = \
            [os.path.join(self.multi_file_excluded_dirs[0], TEST_FILE_NAME)]
        self.base_dir = self.multi_file_config['paths'][0]['base_directory']

        for root, _, files in os.walk(MULTIPLE_DIR):
            self.version_files = \
                [os.path.join(root, f) for f in files if f == 'mock_VERSION']
        self.version_files_without_excluded = \
            [f for f in self.version_files if f != EXCLUDED_FILE]
        self.excluded_files = [f for f in self.version_files if f not
                               in self.version_files_without_excluded]

    def test_get_all_files_no_exclusion(self):
        files = repex._get_all_files(
            filename_regex=TEST_FILE_NAME,
            path=TEST_RESOURCES_DIR_PATTERN,
            base_dir=TEST_RESOURCES_DIR)
        for version_file in self.version_files:
            assert version_file in files

    def test_get_all_files_with_dir_exclusion(self):
        files = repex._get_all_files(
            filename_regex=TEST_FILE_NAME,
            path=TEST_RESOURCES_DIR_PATTERN,
            base_dir=TEST_RESOURCES_DIR,
            excluded_paths=self.multi_file_excluded_dirs)
        for version_file in self.version_files_without_excluded:
            assert version_file in files
        for f in self.excluded_files:
            assert os.path.join(self.base_dir, f) not in files

    def test_get_all_regex_files(self):
        mock_yaml_files = [f for f in os.listdir(TEST_RESOURCES_DIR)
                           if (f.startswith('mock') and f.endswith('yaml'))]
        files = repex._get_all_files(
            filename_regex='mock.*\.yaml',
            path=TEST_RESOURCES_DIR_PATTERN,
            base_dir=TEST_RESOURCES_DIR)
        assert len(mock_yaml_files) == len(files)
        for f in mock_yaml_files:
            assert os.path.join(TEST_RESOURCES_DIR, f) in files

    def test_get_all_regex_files_with_exclusion(self):
        mock_yaml_files = [os.path.join('single', 'mock_VERSION')]
        files = repex._get_all_files(
            filename_regex='mock.*',
            path=TEST_RESOURCES_DIR_PATTERN,
            base_dir=TEST_RESOURCES_DIR,
            excluded_paths=['multiple'],
            excluded_filename_regex='.*yaml',)
        assert len(mock_yaml_files) == len(files)
        for f in mock_yaml_files:
            assert os.path.join(TEST_RESOURCES_DIR, f) in files


class TestMatchReplaceLogic():

    def setup_method(self, test_method):
        self.config = repex._get_config(
            os.path.join(TEST_RESOURCES_DIR, 'match_replace_config.yaml'))
        self.output_file = self.config['paths'][0]['to_file']

    def teardown_method(self, test_method):
        if os.path.isfile(self.output_file):
            os.remove(self.output_file)

    def test_that_replacement_is_only_done_within_match(self):
        """Test that an expression is matched and replacement
        occurs within it alone.

        See `match_replace_*` files for more info.

        The match should include the three first lines in th file.
        The replacement could occur in all four lines.
        Additionally, the match in the first three lines includes
        everything after the version (-1, -2, -3).

        For this test to pass, we expect that not only the fourth line
        remains the same, but that the replacement occurs only according
        to the replacement expression and not the matching expression.
        """
        repex.iterate(config=self.config)
        with open(self.output_file) as f:
            content = f.read().splitlines()
        assert '/something-2.9-1' == content[0]
        assert '/something-2.9-2' == content[1]
        assert '/something-2.9-3' == content[2]
        assert '/something_else-1.3.1-1' == content[3]
