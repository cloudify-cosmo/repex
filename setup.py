import os
import codecs
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


setup(
    name='repex',
    version="1.1.0",
    url='https://github.com/cloudify-cosmo/repex',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    license='LICENSE',
    platforms='All',
    description='sed on steroids',
    long_description=read('README.rst'),
    py_modules=['repex'],
    entry_points={'console_scripts': ['rpx = repex:main']},
    install_requires=[
        "click==6.7",
        "pyyaml==3.12",
        "jsonschema==2.5.1"
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Natural Language :: English',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
