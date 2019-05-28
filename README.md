# intezer-analyze

A cross-platform CLI tool which enables analyzing files with Intezer Analyze.

# Prerequisites
Python 2.7 or 3.5 and above

Python and pip should be available in your path

# Installation

## Windows
`pip install https://github.com/intezer/analyze-cli/archive/master.zip`

**Note**: You might need to restart your command-line session after installing so the command-line will recognize `intezer-analyze` command

## Linux
```
sudo pip install https://github.com/intezer/analyze-cli/archive/master.zip
```

## Mac OS
`sudo pip install --ignore-installed https://github.com/intezer/analyze-cli/archive/master.zip`

# Usage

## Login
To begin using the cli, first you should login with your Intezer Analyze CLI:

`intezer-analyze login <api_key>`
 

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