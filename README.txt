AccessPlusPython (0.29)

Copyright (c) 2003-4 David Boddie

This software is licensed under the MIT License. See the access.py file,
the LICENSE.txt file or http://www.opensource.org/licenses/mit-license.php
for more information.


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
if you wish, in your home directory. On Windows, this will be the %USERPROFILE%
directory. You will also need a MimeMap file from a RISC OS machine. It should
be placed in the same directory as the access.py file.

At this point you are on your own. Read and understand the license again
before proceeding.

If you wish to continue then type

  python access.py

and the application will attempt to create the shares you defined in your
.access file. If this fails, or you want to stop it, CTRL-C will initiate the
application's shutdown sequence.

Killing the process will also stop it but you may find that various threads
are still active and sockets are still in use.

The application tries to work out the correct network settings based on the
system's hostname.  You can tell it to use the network details of a specific
ethernet interface by running

  access.py -i <interface>

If your IP address is on a class C subnet (ie, with netmask 255.255.255.0) then
access.py should work correctly.  If not, then access.py must be modified by
hand to set up its network addresses. Change the "Netmask" variable to match
your netmask. You may also need to change the "Hostaddr" variable if your
hostname resolves to the localhost address (127.0.0.1 or 127.0.1.1).

Firewall

access.py listens on UDP ports 32770, 32771 and 49171.  You must ensure that
these ports are not blocked by your firewall.

Security

Access is not a secure system.  Do not run access.py as root.
