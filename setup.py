from setuptools import setup

install_requires = [
    'requests==2.22.0',
    'future==0.16.0',
    'futures==3.1.1',
    'click==6.7',
    'tenacity==5.0.3',
    'pyjwt==1.6.1',
    'intezer-sdk==0.11'
]
tests_require = [
    'mock==2.0.0',
    'backports.tempfile==1.0',
    'pytest==3.1.2',
    'unittest2==1.1.0',
    'responses==0.10.4'
]

setup(
    name='intezer-analyze-cli',
    version='1.6.1',
    description='Client library for Intezer cloud service',
    author='Intezer Labs ltd.',
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
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
    python_requires='>=3.5',
    zip_safe=False
)
