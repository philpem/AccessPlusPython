AccessPlusPython (0.29)

Copyright (c) 2003-4 David Boddie

This software is licensed under the MIT License. See the access.py file
or http://www.opensource.org/licenses/mit-license.php for more information.


Introduction

This is a snapshot of my Access protocol library which can also be run as a
simple sharing application. It is provided "as is" (read the LICENSE.txt file)
for those who might be interested in developing it further.

It is recommended that you run the application from the directory in which
you unpacked this archive. Hence, there is no real need to use the DistUtils
setup.py script. You can always type

  python setup.py build

if you must.

Before you can share anything with other machines on your local network you
must set up the .access configuration file. The sample configuration file
"dot-access" can be customised to suit your needs then renamed and placed,
if you wish, in your home directory. You will also need a MimeMap file from
a RISC OS machine. It should be placed in the same directory as the access.py
file.

At this point you are on your own. Read and understand the license again
before proceeding.

If you wish to continue then type

  python access.py

and the application will attempt to create the shares you defined in your
.access file. If this fails, or you want to stop it, CTRL-C will initiate the
application's shutdown sequence.

Killing the process will also stop it but you may find that various threads
are still active and sockets are still in use.
