Usage:

Run access.py on a box and share out a directory tree with a large number of
files.  Run createmd5.py to create a file with MD5 sums of all the files in the
tree.

Run RPCEmu.  Mount the ShareFS disc and copy all the contents into a directory
on HostFS.  Run checkmd5.py to ensure there is no data corruption.

Run the same test copying from HostFS to ShareFS.
