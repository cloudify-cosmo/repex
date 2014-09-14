===========
Quick Start
===========

well... all you really need is python and pip.. and..

.. code-block:: bash

 pip install feeder

then you can run

.. code-block:: bash

 mouth feed

and VOILA! (look in your current dir for a "generated.log" file.)


to go beyond feeder gen, run:

.. code-block:: bash

 mouth -h
 mouth list transports # to list the default transports available to you
 mouth list formatters # to list the default formatters available to you
 mouth list fake # for a list of fake data fields you can use

and to configure feeder, see the `configuration <http://feeder.readthedocs.org/en/latest/configuration.html>`_ section.

.. note:: you can use the supplied `vagrantfile <https://github.com/cloudify-cosmo/packman/blob/develop/vagrant/Vagrantfile>`_ which will load a vm with feeder for you..(soon, it will also contain rabbitmq, logstash, elasticsearch and kibana so that you can do some more play.)
