#! /usr/bin/env python

from distutils.core import setup

setup(
    name="AccessPlusPython",
    description="Access+ file sharing protocol handler",
    author="David Boddie",
    author_email="david@boddie.org.uk",
    url="http://www.boddie.org.uk/david/Projects/Python/Access+",
    version="0.15",
    py_modules=["access"],
    scripts=["accessweb.py"]
    )
