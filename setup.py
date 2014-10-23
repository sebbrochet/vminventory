#!/usr/bin/env python

import os
import sys

sys.path.insert(0, os.path.abspath('lib'))
from vminventory import __version__, __author__
from distutils.core import setup

setup(name='vminventory',
      version=__version__,
      description='vCenter inventory update from .vmx files tool',
      long_description='This command-line tool lets you update your vCenter inventory based on .vmx files not already linked to VMs ',
      author=__author__,
      author_email='contact@sebbrochet.com',
      url='https://code.google.com/p/vmmetadata/',
      platforms=['linux'],
      license='MIT License',
      install_requires=['argparse', 'pyvmomi', 'pyyaml'],
      package_dir={'vminventory': 'lib/vminventory'},
      packages=['vminventory'],
      scripts=['bin/vminventory'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX :: Linux',
          'Operating System :: Microsoft :: Windows',
          'Programming Language :: Python',
          'Topic :: System :: Systems Administration',
          ],
      )
