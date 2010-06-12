from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='WebTestRecorder',
      version=version,
      description="",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='wsgi testing unittest doctest webtest',
      author='Ian Bicking',
      author_email='ianb@colorstudy.com',
      url='http://pythonpaste.org/webtestrecorder/',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
