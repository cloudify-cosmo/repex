import os
import codecs
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


setup(
    name='repex',
    version="1.3.1",
    url='https://github.com/cloudify-cosmo/repex',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    license='LICENSE',
    platforms='All',
    description='sed on steroids',
    long_description=read('README.rst'),
    py_modules=['repex'],
    entry_points={'console_scripts': ['rpx = repex:main']},
    install_requires=[
        "click==8.1.2",
        "pyyaml==5.4.1",
        "jsonschema==4.16.0"
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.10',
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
