#! /usr/bin/env python

from distutils.core import setup

import access

setup(
    name="AccessPlusPython",
    description="Access+ file sharing protocol handler",
    author="David Boddie",
    author_email="david@boddie.org.uk",
    url="http://www.boddie.org.uk/david/Projects/Python/AccessPlusPython/",
    version=access.__version__,
    py_modules=["access"]
    )
