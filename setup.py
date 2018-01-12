import os
from setuptools import (
        find_packages,
        setup,
        )


here = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read().strip()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read().strip()
with open(os.path.join(here, 'VERSION')) as f:
    VERSION = f.read().strip()

dependency_links = [
    ]
install_requires = [
    'aiohttp<1.1.0',
    'bs4',
    'discord',
    'hupper',
    'psycopg2',
    'pyyaml',
    'sqlalchemy',
    'requests',
    ]
test_requires = [
    'pytest',
    ]

data_files = [
    ('', ['README.md', 'CHANGES.md', 'VERSION']),
    ]
entry_points = {
    'console_scripts': [
        'initializedb = scripts.initialize_database:main',
        'load-coins = scripts.load_coins:main',
        'make-call = scripts.make_call:main',
        'watch-calls = scripts.watch_calls:main',
    ]
}

setup(name='callbot',
      description='Track crypto calls',
      long_description=README + '\n\n' + CHANGES,
      version=VERSION,
      author='c0lon',
      author_email='',
      dependency_links=dependency_links,
      install_requires=install_requires,
      test_requires=test_requires,
      packages=find_packages(),
      data_files=data_files,
      include_package_data=True,
      entry_points=entry_points
      )
