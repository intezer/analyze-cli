# intezer-analyze

A cross-platform CLI tool which enables analyzing files with Intezer Analyze.

# Prerequisites
Python 3.6 and above

Python and pip should be available in your path

# Installation
`pip install intezer-analyze-cli`

# Usage

## Login
To begin using the cli, first you should login with your API key:

`intezer-analyze login <api_key>`

If you are running the CLI against an on premise deployment, enter the url:

`intezer-analyze login <api_key> http://<address>/api`
 

## Analyze
Send a file or a directory for analysis in Intezer Analyze.

### Usage
`intezer-analyze analyze PATH`

### Parameters
PATH: Path to file or directory to send the files inside for analysis.

###  Examples:
Send a single file for analysis:

    $ intezer-analyze analyze C:\threat.exe

Send all files in directory for analysis:

    $ intezer-analyze analyze C:\files-to-analyze

For complete documentation please run `intezer-analyze analyze --help`
 
## Analyze hashes file
Send a text file with list of hashes

### Usage
`intezer-analyze analyze_by_list PATH`

### Parameters
PATH: Path to txt file.

### Example
Send txt file with hashes for analysis:

    $ intezer-analyze analyze_by_list ~/files/hashes.txt

For complete documentation please run `intezer-analyze analyze_by_list --help`

## Index
Send a file or a directory for indexing

### Usage
`intezer-analyze index PATH INDEX_AS [FAMILY_NAME]`

### Parameters
PATH: Path to file or directory to index

INDEX_AS: `malicious` or `trusted`

FAMILY_NAME: The family name (optional)

### Example
index a single file:
    
    $ intezer-analyze index ~/files/threat.exe.sample malicious family_name
    
index all files in directory:

    $ intezer-analyze index ~/files/files-to-index trusted

For complete documentation please run `intezer-analyze index --help`

## Index hashes file
Send a text file with list of hashes to index

### Usage 
`intezer-analyze index_by_list PATH --index-as=INDEX [FAMILY_NAME]`

### Parameters
PATH: Path to txt file 

--index-as: `malicious` or `trusted`

FAMILY_NAME: The family name (optional)

### Example
Send a file with hashes and verdict for indexing:
 
    $ intezer-analyze index_by_list ~/files/hashes.txt --index-as=malicious family_name

For complete documentation please run `intezer-analyze index --help`

# Troubleshooting
The cli produce a log file named `intezer-analyze-cli.log` in the current working directory.
To enable console output, set the environment variable `INTEZER_DEBUG=1`.