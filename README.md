# intezer-analyze

A cross-platform CLI tool which enables analyzing files with Intezer Analyze.

# Prerequisites
Python 3.5 and above

Python and pip should be available in your path

# Installation
`pip install intezer-analyze-cli`

# Usage

## Login
To begin using the cli, first you should login with your Intezer Analyze CLI:

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
