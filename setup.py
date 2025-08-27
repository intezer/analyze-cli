import os

from setuptools import setup


def rel(*xs):
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), *xs)


with open(rel('intezer_analyze_cli', '__init__.py'), 'r') as f:
    version_marker = '__version__ = '
    for line in f:
        if line.startswith(version_marker):
            _, version = line.split(version_marker)
            version = version.strip().strip("'")
            break
    else:
        raise RuntimeError('Version marker not found.')

install_requires = [
    'click==7.1.2',
    'intezer-sdk>=1.23.0,<2'
]
tests_require = [
    'pytest==8.4.1',
    'responses==0.25.8'
]

with open('README.md') as f:
    long_description = f.read()

setup(
    name='intezer-analyze-cli',
    version=version,
    description='Client library for Intezer cloud service',
    author='Intezer Labs ltd.',
    classifiers=[
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12'
        'Programming Language :: Python :: 3.13'
    ],
    keywords='intezer',
    packages=['intezer_analyze_cli'],
    install_requires=install_requires,
    tests_require=tests_require,
    entry_points='''
        [console_scripts]
        intezer-analyze=intezer_analyze_cli.cli:main_cli
    ''',
    license='Apache License v2',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=3.9',
    zip_safe=False
)
