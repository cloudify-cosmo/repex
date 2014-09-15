repex
=====

|Build Status|

|Gitter chat|

|PyPI|

|PypI|

``jocker`` generates
`Dockerfiles <https://docs.docker.com/reference/builder/>`__ from
`Jinja2 <http://jinja.pocoo.org/docs/dev/>`__ based template files. You
can optionally build an image from the generated file and even more
optionally, push it to a hub.

Requirements
~~~~~~~~~~~~

-  must be run sudo-ically due to Docker's sudo requirement!
-  Python 2.6/2.7 (errr... NO TESTS YET? what a n00b!)
-  `Docker <https://www.docker.com/>`__

Installation
~~~~~~~~~~~~

.. code:: shell

    pip install jocker

Testing
~~~~~~~

Disclaimer in broken english: This like 5 hours project. Tests yet, No.
Hold as test being wroten. Yes.

Usage
~~~~~

.. code:: shell

    jocker -h
    Script to run jokcer via command line

    Usage:
        jocker [--varsfile=<path> --templatefile=<path> --outputfile=<path> --dockerconfig=<path> --dryrun -v]
               [--build=<string>|--push=<string>]
        jocker --version

    Options:
        -h --help                   Show this screen.
        -f --varsfile=<path>        Path to varsfile (if omitted, will assume "vars.py")
        -t --templatefile=<path>    Path to Dockerfile template
        -o --outputfile=<path>      Path to output Dockerfile (if omitted, will assume "Dockerfile")
        -c --dockerconfig=<path>    Path to yaml file containing docker-py configuration
        -d --dryrun                 Whether to actually generate.. or just dryrun
        -b --build=<string>         Image Repository and Tag to build
        -p --push=<string>          Image Repository and Tag to push to (will target --build)
        -v --verbose                a LOT of output (Note: should be used carefully..)
        --version                   Display current version of jocker and exit

Log location
~~~~~~~~~~~~

Jocker log files are generated at ~/.jocker/

Generating
~~~~~~~~~~

-  A ``varsfile`` containing a dict named ``VARS`` should be supplied
   (if omitted, will default to vars.py).
-  A ``templatefile`` should Jinja2-ly correspond with the variables in
   the aforementioned ``VARS`` dict (if omitted, will default to
   Dockerfile.template)
-  An ``outputfile`` should be given (if omitted, will default to
   ``Dockerfile``)

Dryrun
~~~~~~

If Dryrun is specified, the output of the generated template will be
printed. No file will be created.

Build and Push
~~~~~~~~~~~~~~

You can let jocker know that after the Dockerfile was generated, you'd
like to either ``Build`` a Docker image and optionally Push it to your
chosen repository.

Note that for this to work you must be logged in to Docker Hub or your
private images repo from your shell.

Also note that for either of these features to work you MUST be sudo'd
as it's a prerequisite of Docker.

Also also note that you can't specify both --build and --push as --push
triggers a build process anyway.

docker-py configuration for ``build`` and ``push``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A ``dockerconfig`` yaml file can be specified which includes something
like this:

.. code:: yaml

    client:
        base_url: 'unix://var/run/docker.sock'
        version: '1.14'
        timeout: 10
    build:
        quiet: false
        nocache: false
        rm: false
        stream: false
        timeout:
        encoding:

This is the configuration for the docker client and for the build
process as mentioned in https://github.com/docker/docker-py.

If no file was specified, some defaults will be assumed.

Vagrant
~~~~~~~

The Vagrantfile supplied (which I haven't finished yet.. will let you
know once it's ready) will loadz a vbox machine, install docker and
jocker on it, generate a docker image from a template and run a
container based on the image in a daemonized mode to demonstrate the
KRAZIE RAW POWER of jocker (and docker.. I guess *wink*)

Contributing
~~~~~~~~~~~~

Please do.

.. |Build Status| image:: https://travis-ci.org/nir0s/jocker.svg?branch=master
   :target: https://travis-ci.org/nir0s/jocker
.. |Gitter chat| image:: https://badges.gitter.im/nir0s/jocker.png
   :target: https://gitter.im/nir0s/jocker
.. |PyPI| image:: http://img.shields.io/pypi/dm/jocker.svg
   :target: http://img.shields.io/pypi/dm/jocker.svg
.. |PypI| image:: http://img.shields.io/pypi/v/jocker.svg
   :target: http://img.shields.io/pypi/v/jocker.svg
