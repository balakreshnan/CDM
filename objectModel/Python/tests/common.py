﻿# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

from typing import List, Optional
import os
import json
import asyncio

from cdm.enums import CdmStatusLevel
from cdm.objectmodel import CdmCorpusDefinition
from cdm.storage import LocalAdapter, RemoteAdapter
from cdm.utilities import AttributeResolutionDirectiveSet, ResolveOptions


def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper


INPUT_FOLDER_NAME = 'Input'
EXPECTED_OUTPUT_FOLDER_NAME = 'ExpectedOutput'
ACTUAL_OUTPUT_FOLDER_NAME = 'ActualOutput'


class TestHelper:
    # The adapter path to the top-level manifest in the CDM Schema Documents folder. Used by tests where we resolve the corpus.
    # This path is temporarily pointing to the applicationCommon manifest instead of standards due to performance issues when resolving
    # the entire set of CDM standard schemas, after 8000+ F&O entities were added.
    cdm_standards_schema_path = 'local:/core/applicationCommon/applicationCommon.manifest.cdm.json'

    @staticmethod
    def get_schema_docs_root():
        return os.path.join('..', '..', 'schemaDocuments')

    @staticmethod
    def get_input_folder_path(test_subpath: str, test_name: str):
        return TestHelper.get_test_folder_path(test_subpath, test_name, INPUT_FOLDER_NAME)

    @staticmethod
    def get_expected_output_folder_path(test_subpath: str, test_name: str):
        return TestHelper.get_test_folder_path(test_subpath, test_name, EXPECTED_OUTPUT_FOLDER_NAME)

    @staticmethod
    def get_data(test_subpath: str, test_name: str, folder_name: str, file_name: str):
        return json.loads(TestHelper.get_file_content(test_subpath, test_name, folder_name, file_name))

    @staticmethod
    def get_expected_output_data(test_subpath: str, test_name: str, file_name: str):
        return TestHelper.get_data(test_subpath, test_name, EXPECTED_OUTPUT_FOLDER_NAME, file_name)

    @staticmethod
    def get_input_data(test_subpath: str, test_name: str, file_name: str):
        return TestHelper.get_data(test_subpath, test_name, INPUT_FOLDER_NAME, file_name)

    @staticmethod
    def get_input_file_content(test_subpath: str, test_name: str, file_name: str):
        return TestHelper.get_file_content(test_subpath, test_name, INPUT_FOLDER_NAME, file_name)

    @staticmethod
    def get_output_file_content(test_subpath: str, test_name: str, file_name: str):
        return TestHelper.get_file_content(test_subpath, test_name, EXPECTED_OUTPUT_FOLDER_NAME, file_name)

    @staticmethod
    def get_file_content(test_subpath: str, test_name: str, folder_name: str, file_name: str):
        folder_path = TestHelper.get_test_folder_path(test_subpath, test_name, folder_name)
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, 'r') as input_file:
            return input_file.read()

    @staticmethod
    def write_actual_output_file_content(test_subpath: str, test_name: str, file_name: str, file_content: str):
        folder_path = TestHelper.get_actual_output_folder_path(test_subpath, test_name)
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, 'w') as result_file:
            result_file.write(file_content)

    @staticmethod
    def is_file_content_equality(expected: str, actual: str) -> bool:
        expected = expected.replace('\r\n', '\n')
        actual = actual.replace('\r\n', '\n')
        return expected == actual

    @staticmethod
    def get_actual_output_folder_path(test_subpath: str, test_name: str):
        return TestHelper.get_test_folder_path(test_subpath, test_name, ACTUAL_OUTPUT_FOLDER_NAME)

    @staticmethod
    def get_local_corpus(test_subpath: str, test_name: str, test_input_dir: Optional[str] = None):
        test_input_dir = test_input_dir or TestHelper.get_input_folder_path(test_subpath, test_name)
        test_output_dir = TestHelper.get_actual_output_folder_path(test_subpath, test_name)

        cdm_corpus = CdmCorpusDefinition()
        cdm_corpus.ctx.report_at_level = CdmStatusLevel.WARNING
        cdm_corpus.storage.default_namespace = 'local'
        cdm_corpus.storage.mount('local', LocalAdapter(root=test_input_dir))
        cdm_corpus.storage.mount('output', LocalAdapter(root=test_output_dir))
        cdm_corpus.storage.mount('cdm', LocalAdapter('../../schemaDocuments'))
        cdm_corpus.storage.mount('remote', RemoteAdapter(hosts={'contoso': 'http://contoso.com'}))

        return cdm_corpus

    @staticmethod
    def get_test_folder_path(test_subpath: str, test_name: str, folder_name: str):
        test_name = TestHelper.to_pascal_case(test_name)
        test_folder_path = os.path.join('tests', 'testdata', test_subpath, test_name, folder_name)

        if folder_name == ACTUAL_OUTPUT_FOLDER_NAME and not os.path.isdir(test_folder_path):
            os.makedirs(test_folder_path, exist_ok=True)

        return test_folder_path

    @staticmethod
    def to_pascal_case(snake_str: str) -> str:
        if snake_str.find('_') < 0:
            return snake_str

        components = snake_str.split('_')
        return ''.join(x.title() for x in components)

    @staticmethod
    def del_dict_none_values(dict_obj):
        if not isinstance(dict_obj, dict):
            return dict_obj
        for key, value in list(dict_obj.items()):
            if not value:
                del dict_obj[key]
            elif isinstance(value, list):
                dict_obj[key] = list(TestHelper.del_dict_none_values(i) for i in dict_obj[key])
            elif isinstance(value, dict):
                TestHelper.del_dict_none_values(value)
        return dict_obj

    @staticmethod
    def compare_same_object(expected_data, actual_data) -> str:
        expected_data = TestHelper.del_dict_none_values(expected_data)
        actual_data = TestHelper.del_dict_none_values(actual_data)
        return TestHelper.compare_same_object_without_none_values(expected_data, actual_data)

    @staticmethod
    def compare_same_object_without_none_values(expected_data, actual_data) -> str:
        if expected_data is None and actual_data is None:
            return ''

        if expected_data is None or actual_data is None:
            return 'Objects do not match. Expected = {}, actual = {}.'.format(expected_data, actual_data)

        if isinstance(expected_data, list) and isinstance(actual_data, list):
            expected_list = expected_data.copy()
            actual_list = actual_data.copy()

            while expected_list and actual_list:
                index_in_expected = len(expected_list) - 1
                found = False
                for index_in_actual, actual_item in reversed(list(enumerate(actual_list))):
                    if TestHelper.compare_same_object_without_none_values(expected_list[index_in_expected], actual_item) == '':
                        expected_list.pop(index_in_expected)
                        actual_list.pop(index_in_actual)
                        found = True
                        break

                if not found:
                    return 'Lists do not match. Found list member in expected but not in actual : {}.'.format(expected_list[index_in_expected])

            if expected_list:
                return 'Lists do not match. Found list member in expected but not in actual : {}.'.format(expected_list[0])

            if actual_list:
                return 'Lists do not match. Found list member in actual but not in expected : {}.'.format(actual_list[0])

            return ''

        elif isinstance(expected_data, dict) and isinstance(actual_data, dict):
            expected_dict = expected_data.copy()
            actual_dict = actual_data.copy()

            for key in expected_dict.keys():
                if not key in actual_dict:
                    return 'Dictionaries do not match. Found key in exoected but not in actual: {}.'.format(key)

                found_property = TestHelper.compare_same_object_without_none_values(expected_dict[key], actual_dict[key])

                if found_property != '':
                    return 'Value does not match for property {}.'.format(key)

            for key in actual_dict.keys():
                if not key in expected_dict:
                    return 'Value does not match for property {}.'.format(key)

            return ''

        elif expected_data != actual_data:
            return 'Objects do not match. Expected = {}, actual = {}.'.format(expected_data, actual_data)

        return ''


class TestUtils:
    @staticmethod
    async def _get_resolved_entity(corpus: 'CdmCorpusDefinition', input_entity: 'CdmEntityDefinition', resolution_options: List[str], add_res_opt_to_name: Optional[bool] = False) -> 'CdmEntityDefinition':
        """Resolves an entity"""
        ro_hash_set = set()
        for i in range(len(resolution_options)):
            ro_hash_set.add(resolution_options[i])

        resolved_entity_name = ''

        if add_res_opt_to_name:
            file_name_suffix = TestUtils.get_resolution_option_name_suffix(resolution_options)
            resolved_entity_name = 'Resolved_{}{}'.format(input_entity.entity_name, file_name_suffix)
        else:
            resolved_entity_name = 'Resolved_{}'.format(input_entity.entity_name)

        ro = ResolveOptions(input_entity.in_document, directives=AttributeResolutionDirectiveSet(ro_hash_set))

        resolved_folder = corpus.storage.fetch_root_folder('output')
        resolved_entity = await input_entity.create_resolved_entity_async(resolved_entity_name, ro, resolved_folder)

        return resolved_entity

    @staticmethod
    def get_resolution_option_name_suffix(resolution_options: List[str]) -> str:
        """Returns a suffix that contains the file name and resolution option used"""
        file_name_prefix = ''

        for i in range(len(resolution_options)):
            file_name_prefix = '{}_{}'.format(file_name_prefix, resolution_options[i])

        if not file_name_prefix:
            file_name_prefix = '_default'

        return file_name_prefix
