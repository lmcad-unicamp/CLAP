import setuptools

with open("README.md", "r") as f:
    long_description = f.read()
with open("version.txt", "r") as f:
    version = f.read()

setuptools.setup(
    name="clap",
    version=version,
    author="Otavio Napoli",
    author_email="otavio.napoli@gmail.com",
    description="CLAP manages and controls nodes in the cloud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://clap.readthedocs.io",
    packages=setuptools.find_packages(include=['clap.*']),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: GPLv3 License",
        "Operating System :: POSIX :: Linux",
    ],
    install_requires=[
      # Requirements
      'pip>=9.0.0',
      'tinydb==3.15.2',
      'PyYAML',
      'PyCLI',
      'ansible>=2.7',
      'ansible-runner',
      'click>=4.0',
      'coloredlogs',
      'netaddr',
      'paramiko>=2.7',
      'schema',
      'subprocess32',
      # AWS requirements
      'pycrypto',
      'boto>=2.48',
      'boto3',
      'botocore',
      # Other depencencies
      'ipaddress',
      'scandir',
      'secretstorage<=2.3.1',
      'argcomplete',
      # Documentation
      'sphinx',
      'sphinx-autoapi',
      'sphinx_rtd_theme',
      # Server app
      'Flask',
      'Bootstrap-Flask',
      'Flask-SQLAlchemy',
      'Flask-WTF',
      'python-socketio'
    ],
    python_requires='>=3.6'
)
