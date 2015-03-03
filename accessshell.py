#!/usr/bin/env python

import ctypes

"""
accessshell.py

A simple shell front end and peer for Access+
"""

import access, sys
import getopt

share = None
quit = False
current_dir = ""

def concat_path(path, leaf):
 
    # Join 2 RISC OS paths together

    if len(path) > 0:
 
        return path + "." + leaf

    return leaf

def fwshow(p, str):
 
    # Show known Freeway objects

    p.fwshow()

def mount(p, str):
 
    # Mount a ShareFS disc

    global share
    global current_dir

    args = str.split()
 
    if len(args) != 3:
 
        print "Usage: mount <sharename> <ip address>"
 
        return

    current_dir = ""
    share = p.open_share(args[1], args[2])
 
    if share == None:
 
        print "Failed to mount share"

def dir(p, str):
 
    # Change directory

    global current_dir

    if share == None:
 
        print "No share mounted"
 
        return

    i = str.rfind(' ')
    i += 1
    if str[i] == '$':
 
        i += 2
        current_dir = str[i:]
 
    elif str[i] == '^':
 
        dot = current_dir.rfind('.')
 
        if dot == -1:
 
            current_dir = ""
 
        else:
 
            current_dir = current_dir[:dot]
 
    else:

        current_dir = concat_path(current_dir, str[i:])

    # FIXME: Get path info on current_dir to make sure it exists.

def settype(p, str):

    # Set RISC OS filetype of an object

    args = str.split(' ')
 
    if len(args) != 3:
 
        print "Usage: settype <filename> <hex type>"
 
        return

    if share == None:
 
        print "No share mounted"
 
        return

    path = concat_path(current_dir, args[1])
    share.settype(path, int(args[2], base=16))

def cat(p, str):
 
    # Catalogue directory

    global current_dir

    if share == None:
 
        print "No share mounted"
 
        return

    share.cat(current_dir)

def get_file(p, str):
 
    # Copy a file to the local disc

    args = str.split(' ')
    if len(args) != 3:
 
        print "Usage: get_file <remote_file> <local_file>"
 
        return

    if share == None:
 
        print "No share mounted"
 
        return

    f = open(args[2], "wb")
    if not f:
 
        print "Could not open", args[2], "for writing"
 
        return

    str = share.pget(concat_path(current_dir, args[1]))
    f.write(str)
    f.close()
    
def type(p, str):
 
    # Display the contents of a file

    args = str.split(' ')
    if len(args) != 2:
 
        print "Usage: type <filename>"
 
        return
    
    if share == None:
 
        print "No share mounted"
 
        return

    str = share.pget(concat_path(current_dir, args[1]))
    print str

def bye(p, str):
 
    # Exit AccessShell

    global quit

    quit = True

def help(p, str):
 
    # Display help

    print "Access+ shell"
    print "This is a simple shell to view ShareFS shares"
    print "Valid commands:"
    print ".: catalogue current path"
    print "bye: exit Access+ shell"
    print "cat: catalogue current path"
    print "dir <directory>: change directory"
    print "fwshow: show known freeway objects"
    print "get <remote file> <local file>: get a file"
    print "                                doesn't currently work with binary files"
    print "help: this help"
    print "mount <share name> <ip address>: mount a shared disc"
    print "settype <filename>: sets a file's filetype"
    print "type <filename>: print the contents of a file on the screen"
    print ""
    print "Paths are RISC OS style ($.dir1.dir2.filename)"

if __name__ == "__main__":
 
    print "The Access+ shell.  Type 'help' for help"
 
    func_map = {
                ".": cat,
                "bye": bye,
                "cat": cat,
                "dir": dir,
                "fwshow": fwshow,
                "get": get_file,
                "help": help,
                "mount": mount,
                "settype": settype,
                "type": type
               }

    want_access_plus = 1
    try:
        optlist, args = getopt.gnu_getopt(sys.argv[1:], "i:", ["interface=", "no-access-plus"])
    	for o, a in optlist:
    	    if o in ("-i", "--interface"):
    	        access.setup_net(a)
    	    elif o == "--no-access-plus":
    	        want_access_plus = 0
    except getopt.GetoptError, err:
        print err

    p = access.Peer(access_plus = want_access_plus)

    while not quit:
 
        try:
 
            command = raw_input("*")
            space = command.find(' ')
            if space == -1:
 
                cmd = command
 
            else:
 
                cmd = command[0:space]

            if func_map.has_key(cmd):
 
                func_map[cmd](p, command)
 
            else:
 
                print "Invalid command"

        except KeyboardInterrupt:
 
            pass

    p.stop()
    sys.exit()

