########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'elip'

from setuptools import setup

install_requires = [
    'cloudify-rest-client==3.1a3',
    'pika==0.9.13',
    'networkx==1.8.1',
    'proxy_tools==0.1.0'
]

try:
    import importlib  # NOQA
except:
    install_requires.append('importlib==1.0.3')

setup(
    name='cloudify-plugins-common',
    version='3.1a3',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['cloudify', 'cloudify.workflows'],
    license='LICENSE',
    description='Contains necessary decorators and utility methods for '
                'writing Cloudify plugins',
    zip_safe=False,
    install_requires=install_requires
)
