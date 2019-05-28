from setuptools import setup

install_requires = [
    'requests==2.21.0',
    'future==0.16.0',
    'futures==3.1.1',
    'click==6.7',
    'tenacity==5.0.3',
    'enum34==1.1.6;python_version<"3.4"',
    'pyjwt==1.6.1',
    'backports.shutil_which==3.5.1;python_version=="2.7"',
    'intezer-sdk==0.1'
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
    version='1.5.6',
    description='Client library for Intezer cloud service',
    author='Intezer Labs ltd.',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Operating System :: Windows',
        'Operating System :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython'
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
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    zip_safe=False
)
