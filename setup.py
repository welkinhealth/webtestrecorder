from setuptools import setup, find_packages
import os

version = '0.1.1'

here = os.path.dirname(os.path.abspath(__file__))
index = os.path.join(here, 'docs', 'index.txt')
long_description = open(index).read()
long_description = long_description.split('split here', 1)[1].strip()

setup(name='WebTestRecorder',
      version=version,
      description="Record activity from a WSGI application, and generate WebTest tests from that record",
      long_description=long_description,
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Web Environment',
          'License :: OSI Approved :: MIT License',
          'Topic :: Internet :: WWW/HTTP :: WSGI',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          'Topic :: Software Development :: Testing',
          ],
      keywords='wsgi testing unittest doctest webtest',
      author='Ian Bicking',
      author_email='ianb@colorstudy.com',
      url='http://pythonpaste.org/webtestrecorder/',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'WebTest',
          'WebOb>=1.0',
          'Tempita',
          'WSGIProxy',
      ],
      entry_points="""
      [paste.filter_app_factory]
      main = webtestrecorder:Recorder.entry_point
      """,
      )
