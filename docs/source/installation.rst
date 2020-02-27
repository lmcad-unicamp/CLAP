.................................
Installation Guide
.................................

1.  Clone the repository with

::

    git clone https://github.com/lmcad-unicamp/CLAP.git clap

2.  Enter in clap directory with

::

    cd clap

3.  Set the install script to execute with ``chmod`` and run the script!

::

    chmod +x install.sh
    ./install.sh

4.  To use ``clap``, you will need to activate the ``virtual-env``.
    In the ``clap`` root directory run:

::

    source clap-env/bin/activate

5.  Try ``clap``, via the CLI interface:

::

    clapp -vv --show-all-help

To use ``clap`` you will first need to provide some information to launch instances in the cloud.
The :doc:`configuration section <configuration>` section will guide you to write some configuration sections.
After the :doc:`usage section <usage>` will show you how to run ``clap`` commands based on the configurations written.

Section  :doc:`groups <groups>` will show group concepts to run action on several nodes in a row.
Also, the section shows how create your own groups and actions.
