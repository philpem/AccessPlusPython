"""
    access.py
    
    Tools for examining data sent via UDP from an Access+ station.
"""

import glob, os, string, socket, sys, threading, time, types


DEFAULT_FILETYPE = 0xffd
DEFAULT_SUFFIX = os.extsep + "txt"
#DEFAULT_SUFFIX = ""
DEFAULT_SHARE_DELAY = 30.0
TIDY_DELAY = 60.0

# Find the number of centiseconds between 1900 and 1970.
between_epochs = ((365 * 70) + 17) * 24 * 360000

# Buffer size configuration

RECV_SIZE = 16384
RECV_PUT_SIZE = 8192
RECV_GET_SIZE = 8192

SEND_SIZE = 16384
SEND_PPUT_SIZE = 16384
SEND_GET_SIZE = 4096

# Local directory permissions for newly created directories
DIR_EXEC = os.path.stat.S_IFDIR | \
    os.path.stat.S_IXUSR | \
    os.path.stat.S_IXGRP | \
    os.path.stat.S_IXOTH

# Local file permissions for newly created files
FILE_ATTR = os.path.stat.S_IFREG

# Protected share read and write masks
PROTECTED_READ  = 0004
PROTECTED_WRITE = 0002

# Unprotected share read and write masks
UNPROTECTED_READ  = 0444
UNPROTECTED_WRITE = 0222

# Standard sizes of objects on a RISC OS style filing system

ROS_DIR_LENGTH = 0x800


DEBUG = 1

# Host name configuration

# Define a global hostname variable to represent this machine on the local
# subnet.

Hostname = socket.gethostname()

# Convert this name into an address.
Hostaddr = socket.gethostbyname(Hostname)

# Construct a broadcast address.
at = string.rfind(Hostaddr, ".")
Broadcast_addr = Hostaddr[:at] + ".255"

# Use just the hostname from the full hostname retrieved.

at = string.find(Hostname, ".")

if at != -1:

    Hostname = Hostname[:at]


class Common:

    def str2num(self, size, s):
        """Convert a string of decimal digits to an integer."""
        
        i = 0
        n = 0
        while i < size:
        
            n = n | (ord(s[i]) << (i*8))
            i = i + 1
        
        return n
    
    def number(self, size, n):
    
        """Convert a number to a little endian string of bytes for writing to a binary file."""
        
        # Little endian writing
        
        s = ""
        
        while size > 0:
        
            i = n % 256
            s = s + chr(i)
    
            n = n >> 8
            size = size - 1
        
        return s
    
    def read_string(self, data, offset = 0, length = None, ending = None, include = 1):

        """string = read_string(offset, length = None, ending = None, include = 1)
        \r
        \rReturn a string from the object's internal data area, starting at the offset
        \rspecified.
        \r
        \rIf an ending character is given then data will be read until the ending is
        \rfound. If a length is specified then this provides an additional constraint
        \ron the amount of data returned as a string.
        \r
        \rThe include flag determines whether the ending, if given, is returned as
        \rpart of the string.
        """

        if length == None and ending == None:
    
            print 'Internal: Incorrect use of the read_string function.'
            return ""
    
        if length == None:
    
            # Read until one of the endings was found
            new = ''
            while offset < len(data):
    
                c = data[offset]
                if c in ending:
                
                    if include == 1:
                        new = new + c
                    break
                else:
                    new = new + c
                
                offset = offset + 1
    
            return new
    
        elif ending == None:
    
            # Read the number of characters specified
            return data[:length]
    
        else:
            # Read the number of characters specified until an ending is encountered
            new = ''
            for i in range(length):
    
                c = data[offset]
                if c in ending:
                
                    if include == 1:
                        new = new + c
                    break
                else:
                    new = new + c
                
                offset = offset + 1
    
            return new
    
    def coerce(self, fn, args, catch_exceptions, raise_exception, error_msg):
    
        try:
        
            return fn(*args)
        
        except catch_exceptions:
        
            sys.stderr.write(error_msg + "\n")
            raise raise_exception, "Failed to coerce %s using %s." % (args, fn)
    
    def interpret(self, data):
    
        lines = []
        
        i = 0
        
        while i < len(data):
        
            # Print the data in big-endian word form.
            words = []
            j = i
            
            while j < len(data) and j < (i + 16):
            
                if j <= len(data) - 4:
                
                    word = self.str2num(4, data[j:j+4])
                
                else:
                
                    word = self.str2num(len(data) - j, data[j:])
                
                words.append("%08x" % word)
                
                j = j + 4
            
            words = string.join(words, " ")
            
            if len(words) < 35: words = words + (35 - len(words)) * " "
            
            # Show the data in string form.
            s = ""
            
            for c in data[i:i+16]:
            
                if ord(c) > 31 and ord(c) < 127:
                    s = s + c
                else:
                    s = s + "."
            
            lines.append("%s : %s" % (words, s))
            
            i = i + 16
        
        return lines
    
    def from_riscos_time(self, value):
    
        # RISC OS time is given as a five byte block containing the
        # number of centiseconds since 1900 (presumably 1st January 1900).
        
        # Convert the time to the time elapsed since the Epoch (assuming
        # 1970 for this value).
        centiseconds = value - between_epochs
        
        # Convert this to a value in seconds and return a time tuple.
        return time.localtime(centiseconds / 100.0)
        
    def to_riscos_time(self, ttuple = None, seconds = 0):
    
        if ttuple is not None:
        
            # Find the number of seconds since the Epoch using the time tuple
            # given.
            seconds = time.mktime(ttuple)
        
        elif seconds is None:
        
            seconds = time.mktime(self.date)
        
        # Add the number of centiseconds to the number elapsed between 1900
        # and the Epoch (assuming 1970 for this value).
        return long(seconds * 100) + between_epochs
    
    def _make_riscos_filetype_date(self, filetype, cs):
    
        filetype_word = \
            0xfff00000 | (filetype << 8) | \
            ((cs & 0xff00000000) >> 32)
        
        # Date word
        date_word = cs & 0xffffffff
        
        return filetype_word, date_word
    
    def make_riscos_filetype_date(self, path):
    
        # Construct the filetype and date words.
        
        # Determine the relevant filetype to use.
        filetype, discard_filename = self.suffix_to_filetype(path)
        
        # The number of seconds since the last modification
        # to the file is read.
        seconds = os.stat(path)[os.path.stat.ST_MTIME]
        
        # Convert this to the RISC OS date format.
        cs = self.to_riscos_time(seconds = seconds)
        
        return self._make_riscos_filetype_date(filetype, cs)
    
    def take_riscos_filetype_date(self, filetype_word, date_word):
    
        # Extract the filetype and date.
        filetype = (filetype_word & 0xfff00) >> 8
        
        date_str = hex(filetype_word)[-2:] + hex(date_word)[2:]
        date = self.from_riscos_time(long(date_str, 16))
        
        return filetype, date
    



# Sockets and ports

class Ports(Common):

    # Define a dictionary to relate port numbers to the sockets
    # to use. Use the class attributes to ensure that these are
    # only defined once.
    broadcasters = {32770: None, 32771: None, 49171: None}
    ports = {32770: None, 32771: None, 49171: None}
    
    def __init__(self):
    
        # Create sockets to use for polling.
        self._create_poll_sockets()
        
        # Create sockets to use for listening.
        self._create_listener_sockets()
        
        # Create sockets to use for share details.
        self._create_share_sockets()
        
        if DEBUG == 1 and not hasattr(self, "_log"): Ports._log = []
    
    def _create_poll_sockets(self):
    
        if self.broadcasters[32770] is None:
        
            self._poll_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Allow the socket to broadcast packets.
            self._poll_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Set the socket to be non-blocking.
            self._poll_s.setblocking(0)
            
            self._poll_s.bind((Broadcast_addr, 32770))
            
            Ports.broadcasters[32770] = self._poll_s
        
        if self.ports[32770] is None:
        
            # Create a socket for listening.
            self._poll_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set the socket to be non-blocking.
            self._poll_l.setblocking(0)
            
            self._poll_l.bind((Hostaddr, 32770))
            
            Ports.ports[32770] = self._poll_l
    
    def _create_listener_sockets(self):
    
        if self.broadcasters[32771] is None:
        
            self._listen_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Allow the socket to broadcast packets.
            self._listen_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Set the socket to be non-blocking.
            self._listen_s.setblocking(0)
            
            self._listen_s.bind((Broadcast_addr, 32771))
            
            Ports.broadcasters[32771] = self._listen_s
        
        if self.ports[32771] is None:
        
            # Create a socket for listening.
            self._listen_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set the socket to be non-blocking.
            self._listen_l.setblocking(0)
            
            self._listen_l.bind((Hostaddr, 32771))
            
            Ports.ports[32771] = self._listen_l
    
    def _create_share_sockets(self):
    
        if self.broadcasters[49171] is None:
        
            self._share_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Allow the socket to broadcast packets.
            self._share_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Set the socket to be non-blocking.
            self._share_s.setblocking(0)
            
            self._share_s.bind((Broadcast_addr, 49171))
            
            Ports.broadcasters[49171] = self._share_s
        
        if self.ports[49171] is None:
        
            # Create a socket for listening.
            self._share_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set the socket to be non-blocking.
            self._share_l.setblocking(0)
            
            self._share_l.bind((Hostaddr, 49171))
            
            Ports.ports[49171] = self._share_l
    
    def _encode(self, l):
    
        """
        string = _encode(self, list)
        
        Join together the elements in the list supplied to form a string
        which is acceptable to the other Access+ clients.
        """
    
        output = []
        
        for item in l:
        
            if type(item) == types.IntType:
            
                output.append(self.number(4, item))
            
            elif type(item) == types.LongType:
            
                output.append(self.number(4, item))
            
            else:
            
                # Pad the string to fit an integer number of words.
                # If the string is to be terminated by a particular
                # character, it should have been included with the
                # string.
                
                padding = 4 - (len(item) % 4)
                
                if padding == 4: padding = 0
                
                padded = item + (padding * "\000")
                
                output.append(padded)
        
        return string.join(output, "")
    
#    def _decode(self, s, format):
#    
#        """
#        list = _decode(self, string, format)
#        
#        Extract the elements from the string supplied using the format
#        list to a list.
#        """
#    
#        output = []
#        c = 0
#        
#        for i in range(0, len(format)):
#        
#            if type(format[i]item) == types.IntType:
#            
#                output.append(self.number(4, item))
#            
#            else:
#            
#                # Pad the string to fit an integer number of words.
#                padding = 4 - (len(item) % 4)
#                
#                if padding == 4: padding = 0
#                
#                padded = item + (padding * "\000")
#                
#                output.append(padded)
#        
#        return string.join(output, "")
    
    def _send_list(self, l, s, to_addr):
    
        """send_list(self, list, socket, to_addr)
        
        Encode the list as a string suitable for other Access+ clients
        using the _encode method then send it on the socket provided.
        """
        
        self.log("sent", l, to_addr)
        
        s.sendto(self._encode(l), to_addr)
    
    def _expect_reply(self, _socket, msg, host, new_id, commands,
                      tries = 5, delay = 2):
    
        # Add an entry to the Messages object so that replies to this message
        # can be collected rather than being discarded. This requires that
        # the derived class has an attribute called "share_messages" which
        # refers to a Messages instance.
        self.share_messages.add_entry(new_id)
        
        replied = 0
        
        # Keep a record of the time of the previous request.
        t0 = time.time()
        
        while tries > 0:
        
            # See if the response has arrived.
            replied, data = self.share_messages._scan_messages(new_id, commands)
            
            # If a message was found or an error occurred then return
            # immediately.
            if replied != 0:
            
                # Remove the entry in the Messages object for replies to this
                # message.
                self.share_messages.remove_entry(new_id)
                
                return replied, data
            
            t1 = time.time()
            
            if replied == 0 and (t1 - t0) > 1.0:
            
                # Send the request again.
                self._send_list(msg, _socket, (host, 49171))
                
                t0 = t1
                tries = tries - 1
        
        # Remove the entry in the Messages object for replies to this
        # message.
        self.share_messages.remove_entry(new_id)
        
        # Return a negative result.
        return 0, (0, "The machine containing the shared disc does not respond")
    
    def new_id(self):
    
        if not hasattr(self, "_id"):
        
            self._id = 1
        
        else:
        
            self._id = self._id + 0x1001
            if self._id > 0xffffff:
                self._id = 1
        
        return "%s" % self.number(3, self._id)
    
    def _send_request(self, msg, host, commands, new_id = None, tries = 5,
                      delay = 2):
    
        """replied, data = _send_reqest(self, msg)
        
        Send a message via the non-broadcast share port to a remote client
        and wait for a reply.
        """
        # Use the non-broadcast socket.
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return 0, []
        
        s = self.ports[49171]
        
        if new_id is None:
        
            # Use a new ID for this message.
            new_id = self.new_id()
        
        # Create the command to send. The three bytes following the
        # command character are used to identify the response from the
        # other client (it passes them back in its response).
        msg[0] = msg[0] + new_id
        
        # Send the request.
        self._send_list(msg, s, (host, 49171))
        
        # Wait for a reply.
        replied, data = \
            self._expect_reply(s, msg, host, new_id, commands, tries, delay)
        
        #if replied == 1:
        #
        #    self.log("received", data, (host, 49171))
        #
        #else:
        #
        #    # The data value is a tuple if an error occurs.
        #    self.log("received", data[1], (host, 49171))
        
        return replied, data
    
    def log(self, direction, data, address):
    
        if DEBUG == 0: return
        
        if direction[0] == "s" and type(data) == types.ListType:
        
            lines = ["Sent to %s:%i" % address] + \
                self.interpret(self._encode(data))
                
            Ports._log = Ports._log + lines
        
        elif direction[0] == "s" and type(data) == types.StringType:
        
            lines = ["Sent to %s:%i" % address] + \
                self.interpret(data)
                
            Ports._log = Ports._log + lines
        
        elif direction[0] == "r":
        
            lines = ["Received from %s:%i" % address] + \
                self.interpret(data)
            
            Ports._log = Ports._log + lines
        
        else:
        
            Ports._log.append(data)
        
        Ports._log.append("")
    
    def write_log(self, path):
    
        open(path, "w").writelines(map(lambda x: x + "\n", Ports._log))



class Files:

    def __init__(self):
    
        # Keep a dictionary of local file handles in use but limit its length.
        self.max_handles = 100
        self.handles = {}
    
    def __getitem__(self, item):
    
        # Return the item as in a normal dictionary.
        return self.handles[item]
    
    def __setitem__(self, item, value):
    
        # Add an entry as in a normal handles.
        self.handles[item] = value
    
    def __delitem__(self, item):
    
        del self.handles[item]
    
    def __cmp__(self, other):
    
        if isinstance(other, Match):
        
            return self.handles == other.handles
        
        else:
        
            return self == other
    
    def clear(self):
    
        return self.handles.clear()
    
    def copy(self):
    
        return self.handles.copy()
    
    def get(self, item, default = None):
    
        return self.handles(item, default)
    
    def has_key(self, item):
    
        return self.handles.has_key(item)
    
    def items(self):
    
        return self.handles.items()
    
    def keys(self):
    
        return self.handles.keys()
    
    def popitem(self):
    
        return self.handles.popitem()
    
    def setdefault(self, item, default = None):
    
        return self.handles.setdefault(item, default)
    
    def update(self, dict):
    
        return self.handles.update(dict)
    
    def values(self):
    
        return self.handles.values()


class Messages(Common):

    def __init__(self):
    
        self.messages = {}
    
    def __getitem__(self, item):
    
        # Return the item as in a normal dictionary.
        return self.messages[item]
    
    def __setitem__(self, item, value):
    
        # Add an entry as in a normal messages.
        self.messages[item] = value
    
    def __delitem__(self, item):
    
        del self.messages[item]
    
    def __cmp__(self, other):
    
        if isinstance(other, Match):
        
            return self.messages == other.messages
        
        else:
        
            return self == other
    
    def __len__(self):
    
        return len(self.messages)
    
    def clear(self):
    
        return self.messages.clear()
    
    def copy(self):
    
        return self.messages.copy()
    
    def get(self, item, default = None):
    
        return self.messages(item, default)
    
    def has_key(self, item):
    
        return self.messages.has_key(item)
    
    def items(self):
    
        return self.messages.items()
    
    def keys(self):
    
        return self.messages.keys()
    
    def popitem(self):
    
        return self.messages.popitem()
    
    def setdefault(self, item, default = None):
    
        return self.messages.setdefault(item, default)
    
    def update(self, dict):
    
        return self.messages.update(dict)
    
    def values(self):
    
        return self.messages.values()
    
    def append(self, value):
    
        # Take the first word of the message and store the message under
        # that entry in the dictionary if it exists.
        key = value[1:4]
        
        if key != "" and self.messages.has_key(key):
        
            self.messages[key].append(value)
    
    def remove(self, value):
    
        # Take the first word of the message and remove the message from
        # that entry in the dictionary if it exists.
        key = value[1:4]
        
        if key != "" and self.messages.has_key(key):
        
            self.messages[key].remove(value)
    
    def add_entry(self, new_id):
    
        # Add a dictionary entry for expected messages with this ID.
        self.messages[new_id] = []
    
    def remove_entry(self, new_id):
    
        # Remove dictionary entries for messages which are no longer valid.
        del self.messages[new_id]
    
    def _scan_messages(self, new_id, commands):
    
        for data in self.messages[new_id]:
        
            for command in commands:
            
                if data[:4] == command + new_id:
                
                    # Remove the claimed message from the list.
                    self.messages[new_id].remove(data)
                    
                    #self.data = data
                    
                    # Reply indicating that valid data was received.
                    return 1, data
                
            if data[:4] == "E"+new_id:
            
                #print 'Error: "%s"' % data[8:]
                self.messages[new_id].remove(data)
                
                return -1, (self.str2num(4, data[4:8]), data[8:])
        
        # Return a negative result.
        return 0, (0, "The machine containing the shared disc does not respond")
    
    def _all_messages(self, new_id, commands):
    
        try:
        
            reply_messages = self.messages[new_id]
        
        except KeyError:
        
            reply_messages = []
        
        messages = []
        
        for data in reply_messages:
        
            for command in commands:
            
                if data[:4] == command + new_id:
                
                    # Remove the claimed message from the list.
                    self.messages[new_id].remove(data)
                    
                    # Add it to the list of messages found.
                    messages.append(data)
        
        return messages
    



class ConfigError(Exception):

    pass



class File:

    def __init__(self, path, share):
    
        self.pieces = []
        self.ptr = 0
        self.path = path
        
        # The share the file is stored in.
        self.share = share
        
        if os.path.exists(path):
        
            self._length = os.path.getsize(path)
        
        else:
        
            # Create the object.
            open(path, "wb").write("")
            self._length = 0
    
    def tell(self):
    
        return self.ptr
    
    def seek(self, ptr, from_end):
    
        if from_end == 0:
        
            self.ptr = ptr
        
        elif from_end == 1:
        
            self.ptr = self.ptr + ptr
        
        else:
        
            self.ptr = self._length - ptr
    
    def read(self, length):
    
        if self.pieces != []:
        
            # Not done yet. Write the pieces first then read back the
            # result.
            self.close()
        
        if self.pieces == []:
        
            # If there are pieces in the object then read the data from
            # the underlying file.
            try:
            
                f = open(self.path, "rb")
                f.seek(self.ptr, 0)
                file_data = f.read(length)
                self.ptr = f.tell()
                f.close()
                
                return file_data
            
            except IOError:
            
                # Maybe we should allow this to be thrown.
                return ""
    
    def write(self, data):
    
        self.pieces.append( (self.ptr, data) )
        self.ptr = self.ptr + len(data)
        self._length = max(self.ptr, self._length)
    
    def length(self):
    
        if self.pieces != []:
        
            # If there are pieces in the object then determine the file
            # length from the internal variable.
            return self._length
        
        else:
        
            # Otherwise, determine the actual file's length.
            return os.path.getsize(self.path)
    
    def set_length(self, length):
    
        self._length = length
    
    def close(self):
    
        if self.pieces == []:
        
            return
        
        try:
        
            # Zero the contents of the file.
            f = open(self.path, "wb")
            
            f.write("\x00" * self._length)
            
            f.close()
            
            f = open(self.path, "wb+")
            
            # Write all the pieces to the path specified at initialisation.
            for ptr, data in self.pieces:
            
                f.seek(ptr, 0)
                f.write(data)
            
            f.flush()
            
            # Truncate the file.
            f.truncate(self._length)
            
            f.close()
        
        except IOError:
        
            pass
        
        # Remove data now that it has been written.
        self.pieces = []


class Buffer:

    def __init__(self):
    
        self.pieces = []
        self.ptr = 0
        self._length = 0
    
    def read(self):
    
        # Assume data fragments in the buffer do not overlap.
        self.pieces.sort()
        
        data = reduce(lambda x, y: x + y[1], self.pieces, "")
        
        return data
    
    def write(self, data):
    
        self.pieces.append( (self.ptr, data) )
        self.ptr = self.ptr + len(data)
        self._length = max(self.ptr, self._length)
    
    def seek(self, ptr, from_end):
    
        if from_end == 0:
        
            self.ptr = ptr
        
        elif from_end == 1:
        
            self.ptr = self.ptr + ptr
        
        else:
        
            self.ptr = self._length - ptr
    
    def length(self):
    
        return self._length
    
    def set_length(self, length):
    
        self._length = length
    
    def close(self):
    
        # Do nothing.
        return

class Directory:

    def __init__(self, path, share):
    
        if not os.path.exists(path):
        
            try:
            
                os.mkdir(path)
                os.chmod(path, share.mode | DIR_EXEC)
                self.log(
                    "comment",
                    "Created %s with permissions: %s" % \
                        (path, oct(share.mode | DIR_EXEC)),
                    ""
                    )
            
            except OSError:
            
                pass
        
        self.path = path
        self.share = share
    
    def length(self):
    
        return ROS_DIR_LENGTH


class Unused(Common):

    def _read_port(self, port):
    
        if not self.ports.has_key(port):
        
            print "No socket to use for port %i" % port
            return []
        
        s = self.ports[port]
        
        try:
        
            data, address = s.recvfrom(RECV_SIZE)
            
            lines = ["From: %s:%i" % address]
            lines = lines + self.interpret(data)
        
        except socket.error:
        
            lines = []
        
        return lines
    
    def read_port(self, ports = [32770, 32771, 49171]):
    
        t0 = time.time()
        
        log = []
        
        try:
        
            while 1:
            
                t = int(time.time() - t0)
                
                for port in ports:
                
                    lines = self._read_port(port)
                    
                    if lines != []:
                    
                        for line in lines:
                        
                            print line
                            log.append(line)
                        
                        print
                        log.append("")
        
        except KeyboardInterrupt:
        
            pass
        
        return log



class ShareError(Exception):

    pass


class Translate:

    def __init__(self, directory = None):
    
        # Look for a MimeMap file in the path used to invoke this program.
        path, file = os.path.split(sys.argv[0])
        
        paths = [ "MimeMap",
                  os.path.join(path, "MimeMap") ]
        
        if directory is not None:
        
            paths.append(os.path.join(directory, os.extsep+"MimeMap"))
        
        self.create_mimemap(paths)
    
    def create_mimemap(self, paths):
    
        # Compile a list of paths to check for the MimeMap file.
        
        f = None
        
        for path in paths:
        
            try:
            
                f = open(path, "r")
                break
            
            except IOError:
            
                # Loop again.
                pass
        
        if f is None:
        
            print "Failed to find MimeMap file."
            lines = []
        
        else:
        
            lines = f.readlines()
            f.close()
        
        mappings = []
        
        # Read the lines found.    
        for line in lines:
        
            # Strip leading and trailing whitespace and split the string.
            s = string.strip(line)
            
            values = []
            current = ""
            
            # Ignore lines beginning with a "#" character.
            if s[:1] == "#": continue
            
            for c in s:
            
                if c not in string.whitespace:
                
                    current = current + c
                
                elif current != "":
                
                    values.append(current)
                    current = ""
            
            if current != "":
            
                values.append(current)
            
            # The values correspond to various fields; the first is the
            # MIME type/subtype; the second is the RISC OS name; the third
            # is the hexadecimal value used for the filetype; the rest
            # are the extensions to recognise:
            if len(values) > 3:
            
                mappings.append(
                    { "MIME": values[0], "RISC OS name": values[1],
                      "Hex": values[2], "Extensions": values[3:] }
                    )
        
        # Store the mappings.
        self.mimemap = mappings
    
    # Define dictionaries to use to translate filename.
    to_riscos = {os.extsep: "/", " ": "\xa0", os.sep: "."}
    from_riscos = {"/": os.extsep, "\xa0": " ", ".": os.sep}
    
    def _filename(self, name, dict):
    
        new = []
        
        for c in name:
        
            if dict.has_key(c):
            
                new.append(dict[c])
            
            else:
            
                new.append(c)
        
        return string.join(new, "")
    
    def to_riscos_filename(self, name):
    
        return self._filename(name, self.to_riscos)
    
    def from_riscos_filename(self, name):
    
        return self._filename(name, self.from_riscos)
    
    def suffix_to_filetype(self, filename, present = "truncate"):
    
        # Find the appropriate filetype to use for the filename given.
        at = string.rfind(filename, os.extsep)
        
        if at == -1:
        
            # No suffix: return the default filetype.
            return DEFAULT_FILETYPE, self.to_riscos_filename(filename)
        
        # The suffix includes the "." character. Remove this platform's
        # separator and replace it with a ".".
        suffix = "." + filename[at+len(os.extsep):]
        
        # Find the suffix in the list of mappings.
        for mapping in self.mimemap:
        
            if suffix in mapping["Extensions"]:
            
                # Return the corresponding filetype for this suffix.
                try:
                
                    if present == "truncate":
                    
                        # Remove the suffix before presenting it to RISC OS.
                        return string.atoi(mapping["Hex"], 16), \
                            self.to_riscos_filename(filename)[:at]
                    
                    else:
                    
                        return string.atoi(mapping["Hex"], 16), \
                            self.to_riscos_filename(filename)
                   
                except ValueError:
                
                    # The value found was not in a valid hexadecimal
                    # representation. Return the default filetype.
                    return DEFAULT_FILETYPE, \
                        self.to_riscos_filename(filename)
        
        # Check whether the filename included a hexadecimal suffix.
        try:
        
            value = string.atoi(suffix[len(os.extsep):], 16)
        
        except ValueError:
        
            # No mappings declared the suffix used.
            return DEFAULT_FILETYPE, self.to_riscos_filename(filename)
        
        # A hexadecimal suffix was used.
        if present == "truncate":
        
            # Remove the suffix before presenting it to RISC OS.
            return value, self.to_riscos_filename(filename)[:at]
        
        else:
        
            return value, self.to_riscos_filename(filename)
    
    def filetype_to_suffix(self, filename, filetype, present = "truncate"):
    
        # Find the appropriate filetype to use for the filename given.
        #at = string.rfind(filename, "/")
        #
        #if at != -1 and present == "suffix":
        if present == "suffix":
        
            # The suffix includes the "/" character. Replace it with this
            # platform's separator and ignore the filetype.
            return self.from_riscos_filename(filename)
        
        # Otherwise append a suffix to the filename to represent the
        # filetype.
        
        # Find a choice of suffixes to use in the list of mappings.
        suffixes = None
        
        for mapping in self.mimemap:
        
            # Convert the MimeMap entry's filetype to a string.
            if filetype == string.atoi(mapping["Hex"], 16):
            
                # Return the first corresponding suffix.
                try:
                
                    suffixes = mapping["Extensions"]
                    
                    if len(suffixes) > 0:
                    
                        break
                
                except KeyError:
                
                    pass
        
        if suffixes is not None:
        
            # Choose the first available suffix.
            return self.from_riscos_filename(filename) + \
                os.extsep + suffixes[0][1:]
        
        else:
        
            # No mappings declared the filetype used. Append a suffix
            # containing the three digit hexadecimal filetype value to the
            # end of the name.
            return self.from_riscos_filename(filename) + os.extsep + \
                "%03x" % filetype
    
    def find_relevant_file(self, path, suffix = None):
    
        """find_relevant_file(self, path, suffix = None)
        
        Given a path for a file without a suffix from RISC OS, find the
        relevant file on our machine. This relies on the bodies of the
        filenames being unique.
        
        If a suffix is passed this makes the job much easier.
        """
        
        if suffix is None:
        
            suffix = ""
            
        paths = [path + suffix, path + DEFAULT_SUFFIX, path + os.extsep + "*"]
        
        # Look for a file with any suffix that matches
        # the path given.
        
        path = None
        
        for path in paths:
        
            files = glob.glob(path)
            
            if len(files) == 1:
            
                # Unique match
                return files[0]
        
        return None
    
    def construct_directory_name(self, elements):
    
        built = ""
        
        for element in elements:
        
            built = os.path.join(built, element)
        
        return built
    
    def read_mode(self, path):
    
        """mode = read_mode(self, path)
        
        Return the access mode for the path given or None if the path is
        invalid.
        """
        
        try:
        
            return os.stat(path)[os.path.stat.ST_MODE]
        
        except OSError:
        
            return None
    
    def to_riscos_access(self, mode = None, path = None):
    
        """word = to_riscos_access(self, mode = None, path = None)
        
        Return a word representing the RISC OS access flags roughly
        equivalent to the read, write and execute flags for a local file,
        given as an octal number in integer form.
        
        If a path is given then its mode is determined and used instead.
        
        If no valid mode value can be determined then 0444 is used.
        """
        
        if path is not None:
        
            mode = self.read_mode(path)
        
        if mode is None:
        
            mode = 0444
        
        # Owner permissions
        owner_read = (mode & os.path.stat.S_IRUSR) != 0
        owner_write = ((mode & os.path.stat.S_IWUSR) != 0) << 1
        owner_execute = ((mode & os.path.stat.S_IXUSR) != 0) << 2
        
        owner = owner_read | owner_write | owner_execute
        
        # Ignore group permissions.
        
        # Permissions for others
        others_read = ((mode & os.path.stat.S_IROTH) != 0) << 4
        others_write = ((mode & os.path.stat.S_IWOTH) != 0) << 5
        #others_execute = (mode & os.path.stat.S_IXOTH) != 0
        
        others = others_read | others_write
        
        return owner | others
    
    def from_riscos_access(self, word):
    
        """mode = from_riscos_access(self, word)
        
        Return a mode value representing the read, write and execute flags
        for a local file, given as an octal number in integer form roughly
        equivalent to the RISC OS access flags.
        """
        
        # Owner permissions
        owner_read = ((word & 0x01) != 0) * os.path.stat.S_IRUSR
        owner_write = ((word & 0x02) != 0) * os.path.stat.S_IWUSR
        owner_execute = ((word & 0x04) != 0) * os.path.stat.S_IXUSR
        
        owner = owner_read | owner_write | owner_execute
        
        # Permissions for others
        others_read = ((word & 0x10) != 0) * os.path.stat.S_IROTH
        others_write = ((word & 0x20) != 0) * os.path.stat.S_IWOTH
        
        others = others_read | others_write
        
        # Group permissions
        group = others
        
        return owner | group | others
    
    def repr_mode(self, mode):
    
        """string = repr_mode(self, mode)
        
        Returns a string showing the access permissions for a file, given
        as an octal number in integer form.
        """
        
        # Use shortcuts to construct a string with as little code as
        # possible.
        
        # Owner permissions
        ow_r = ["-", "r"][(mode & os.path.stat.S_IRUSR) != 0]
        ow_w = ["-", "w"][(mode & os.path.stat.S_IWUSR) != 0]
        ow_e = ["-", "x"][(mode & os.path.stat.S_IXUSR) != 0]
        
        owner = ow_r + ow_w + ow_e
        
        # Group permissions.
        g_r = ["-", "r"][(mode & os.path.stat.S_IRGRP) != 0]
        g_w = ["-", "w"][(mode & os.path.stat.S_IWGRP) != 0]
        g_e = ["-", "x"][(mode & os.path.stat.S_IXGRP) != 0]
        
        group = g_r + g_w + g_e
        
        # Permissions for others
        ot_r = ["-", "r"][(mode & os.path.stat.S_IROTH) != 0]
        ot_w = ["-", "w"][(mode & os.path.stat.S_IWOTH) != 0]
        ot_e = ["-", "x"][(mode & os.path.stat.S_IXOTH) != 0]
        
        others = ot_r + ot_w + ot_e
        
        return owner + group + others
    
    def to_riscos_objtype(self, path):
    
        if not os.path.exists(path):
        
            return 0
        
        elif os.path.isfile(path):
        
            return 0x0101
        
        elif os.path.isdir(path):
        
            return 0x2
        
        else:
        
            return 0
    
    def from_riscos_path(self, ros_path, find_obj = 1):
    
        # Construct a path to the object below the shared directory.
        path = self.from_riscos_filename(ros_path)
        
        # Append this path to the shared directory's path.
        path = os.path.join(self.directory, path)
        
        if find_obj == 1:
        
            # Look for a suitable file.
            path = self.find_relevant_file(path)
        
        return path
    
    def read_path_info(self, path):
    
        # Determine the file's relevant filetype and
        # date words.
        filetype, date = self.make_riscos_filetype_date(path)
        
        # Find the length of the file.
        if os.path.isdir(path):
        
            length = ROS_DIR_LENGTH
        
        else:
        
            length = os.path.getsize(path)
        
        # Construct access attributes for the other client.
        access_attr = self.to_riscos_access(path = path)
        
        # Use a default value for the object type.
        object_type = self.to_riscos_objtype(path = path)
        
        # Use the inode of the file as its handle.
        handle = os.stat(path)[os.path.stat.ST_INO]# & 0xffffff7f
        
        return filetype, date, length, access_attr, object_type, handle
    


class Share(Ports, Translate):

    """Share
    
    A class encapsulating a share on a local or remote machine.
    """
    
    def __init__(self, name, directory, mode, delay, present, filetype,
                 file_handler):
    
        # Call the initialisation method of the base classes.
        Ports.__init__(self)
        Translate.__init__(self, directory = directory)
        
        # Keep a reference to the parent objects file handler.
        self.file_handler = file_handler
        
        # Determine the protected flag to broadcast by examining the
        # other users write bit.
        if (mode & os.path.stat.S_IWOTH) == 0:
        
            self.protected = 1
            self.read_mask = PROTECTED_READ
            self.write_mask = PROTECTED_WRITE
        
        else:
        
            self.protected = 0
            self.read_mask = UNPROTECTED_READ
            self.write_mask = UNPROTECTED_WRITE
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.event = event
        
        # Create a thread to run the share broadcast loop.
        thread = threading.Thread(
            group = None, target = self.broadcast_share,
            name = 'Share "%s"' % name, args = (name, event),
            kwargs = {"protected": self.protected, "delay": delay}
            )
        
        # Determine the current time to use for the date of creation.
        date = time.localtime(time.time())
        
        # Record the relevant information about the share.
        
        self.name = name
        self.thread = thread
        self.directory = directory
        self.date = date
        self.mode = mode
        self.present = present
        self.filetype = filetype
        
        # Convert the share's mode mask to a file attribute mask.
        self.access_attr = self.to_riscos_access(mode = mode)
        
        # Start the thread.
        thread.start()
    
    def broadcast_share(self, name, event, protected = 0, delay = 30):
    
        """broadcast_share(self, name, event, protected = 0, delay = 30)
        
        Broadcast the availability of a share every few seconds.
        """
        
        # Broadcast the availability of the share on the polling socket.
        
        if not self.broadcasters.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010002, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        # Broadcast a notification to other clients.
        
        for i in range(0, 5):
        
            self._send_list(data, s, (Broadcast_addr, 49171))
            
            time.sleep(1)
        
        # Remind other clients of the availability of this share.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010004, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
        
        while 1:
        
            self._send_list(data, s, (Broadcast_addr, 32770))
            
            t0 = time.time()
            
            while (time.time() - t0) < delay:
            
                if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010003, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
    
    #def notify_share_users(self, 
    
    def descend_path(self, path, names = None, check_mode = PROTECTED_READ):
    
        """path = descend_path(self, path, names = None)
        
        Descend the path as far as the share's access attributes will allow.
        If this is not far enough then return None.
        
        Similarly, if the path takes us outside the share then return None.
        """
        
        if names is None: names = []
        
        if path == self.directory:
        
            return self.directory, names
        
        # Split the path into two parts.
        path1, path2 = os.path.split(path)
        
        # Recurse with a path and a list of names to descend into.
        path, names = self.descend_path(path1, [path2] + names)
        
        # Try to descend the directory structure.
        
        # If there are no names to add to the path then just return the path
        # and an empty list.
        if names == []:
        
            return path, []
        
        # Join the first name to the path.
        next_path = os.path.join(path, names[0])
        
        mode = self.read_mode(next_path)
        
        if mode is None or (mode & check_mode & self.mode) == 0:
        
            # We cannot read this object. Return the unextended path and the
            # names which were not added.
            return path, names
        
        # We can read this object so return the combined path and a shortened
        # list of names.
        return next_path, names[1:]
    
    def open_path(self, ros_path):
    
        self.log("comment", "Original path: %s" % ros_path, "")
        
        # Convert the RISC OS style path to a path within the share.
        path = self.from_riscos_path(ros_path)
        
        if ros_path == "":
        
            # Return information about the share itself.
            cs = self.to_riscos_time()
            
            filetype_word, date_word = \
                self._make_riscos_filetype_date(0xfcd, cs)
            
            # Mask the access attributes of this file with the share's access
            # mask.
            access_attr = self.access_attr
            
            # Set the filetype to be a share (0xfcd), the date as
            # the time when the share was added, the length as
            # a standard value, the access attributes are
            # converted from the mode value given and the object
            # type as a standard value.
            return [ filetype_word, date_word, ROS_DIR_LENGTH, access_attr,
                     0x102, 0], path

        self.log("comment", "Open path: %s" % path, "")
        
        # Find whether the directory structure can be legitimately descended.
        if path is not None:
        
            path, rest = self.descend_path(path, check_mode = self.read_mask)
            
            if rest != []: path = None
        
        if path is not None and os.path.isdir(path):
        
            # A directory
            
            filetype, date, length, access_attr, object_type, handle = \
                self.read_path_info(path)
            
            # Keep this handle for possible later use.
            if not self.file_handler.has_key(handle):
            
                self.file_handler[handle] = Directory(path, self)
            
            else:
            
                # It may be necessary to report an error that the handle
                # is in use.
                pass
            
            return [ filetype, date, length, access_attr, object_type,
                     handle ], path
        
        elif path is not None and os.path.isfile(path):
        
            # A file
            
            filetype, date, length, access_attr, object_type, \
                handle = self.read_path_info(path)
            
            # Keep this handle for possible later use.
            if not self.file_handler.has_key(handle):
            
                self.file_handler[handle] = File(path, self)
            
            else:
            
                # It may be necessary to report an error that the handle
                # is in use.
                fh = self.file_handler[handle]
                
                # Use the file object's length, if possible.
                length = fh.length()
            
            return [ filetype, date, length, access_attr, object_type,
                     handle ], path
        
        else:
        
            # Reply with an error message.
            return None, path
    
    def create_file(self, ros_path):
    
        # Try to open the corresponding file.
        info, path = self.open_path(ros_path)
        
        if ros_path == "":
        
            # The share itself is being referenced.
            return None, path
        
        if info is None:
        
            # No file exists at this path.
            
            # Determine whether the parent directory of the file can be written
            # to.
            
            # Construct a path to the object below the shared directory.
            path = self.from_riscos_path(ros_path, find_obj = 0)
            
            parent_path, file = os.path.split(path)
            
            write_path, rest = self.descend_path(
                parent_path, check_mode = self.write_mask
                )
            
            # Return an error value if it can't.
            if rest != []: return None, write_path
            
            try:
            
                # Create an object on the local filesystem.
                path = path + DEFAULT_SUFFIX
                open(path, "wb").write("")
                os.chmod(path, self.mode | FILE_ATTR)
            
            except IOError:
            
                return None, path
            
            except OSError:
            
                os.remove(path)
                return None, path
        
        else:
        
            # A file already exists at this path.
            
            # Find whether the object can be legitimately overwritten.
            path, rest = self.descend_path(path, check_mode = self.write_mask)
            
            # Return an error value if it can't.
            if rest != []: return None, path
            
            try:
            
                # Create an object on the local filesystem.
                open(path, "wb").write("")
                os.chmod(path, self.mode | FILE_ATTR)
            
            except IOError:
            
                return None, path
            
            except OSError:
            
                os.remove(path)
                return None, path
        
        self.log("comment", "Actual path: %s" % path, "")
        
        # Try to find the details of the object.
        
        if os.path.isdir(path):
        
            # A directory
            
            filetype, date, length, access_attr, object_type, \
                handle = self.read_path_info(path)
            
            # Keep this handle for possible later use.
            if not self.file_handler.has_key(handle):
            
                self.file_handler[handle] = Directory(path, self)
            
            return [ filetype, date, length, access_attr, object_type,
                     handle ], path
        
        elif os.path.isfile(path):
        
            # A file
            
            filetype, date, length, access_attr, object_type, \
                handle = self.read_path_info(path)
            
            # Keep this handle for possible later use.
            if not self.file_handler.has_key(handle):
            
                self.file_handler[handle] = File(path, self)
            
            else:
            
                # It may be necessary to report an error that the handle
                # is in use.
                fh = self.file_handler[handle]
                
                # Use the file object's length, if possible.
                length = fh.length()
            
            return [ 0xdeaddead, 0xdeaddead, length, 0x33, object_type,
                     handle ], path
        
        else:
        
            # Reply with an error message.
            return None, path
    
    def delete_path(self, ros_path):
    
        # Convert the RISC OS style path to a path within the share.
        path = self.from_riscos_path(ros_path)
        
        if ros_path == "":
        
            # The share itself is being referenced.
            return None, path
        
        if path is None:
        
            return None, path
        
        # Find whether the directory structure can be legitimately descended.
        path, rest = self.descend_path(path, check_mode = self.write_mask)
        
        if rest != []:
        
            return None, path
        
        self.log("comment", "Delete request: %s" % path, "")
        
        filetype, date, length, access_attr, object_type, \
            handle = self.read_path_info(path)
        
        try:
        
            if os.path.isfile(path):
            
                os.remove(path)
            
            elif os.path.isdir(path):
            
                os.rmdir(path)
            
            else:
            
                return None, path
            
            return [ filetype, date, length, access_attr,
                     object_type ], path
        
        except OSError:
        
            return None, path
    
    def set_access_attr(self, ros_path, access_attr):
    
        # Convert the RISC OS style path to a path within the share.
        path = self.from_riscos_path(ros_path)
        
        if ros_path == "":
        
            # The share itself is being referenced.
            return None, path
        
        if path is None:
        
            return None, path
        
        # Find whether the directory structure can be legitimately descended.
        path, rest = self.descend_path(path, check_mode = self.write_mask)
        
        if rest != []:
        
            return None, path
        
        # Convert the RISC OS attributes to a mode value.
        mode = self.from_riscos_access(access_attr)
        
        # Try to change the permissions on the object.
        try:
        
            if os.path.isfile(path):
            
                # Ensure that the remote client doesn't mess up the file
                # access attributes by making the file unreadable.
                mode = (
                    (mode & 0x1c0) | ((mode & 0x1c0) >> 3) | \
                    ((mode & 0x1c0) >> 6)
                    )
                
                mode = (mode & self.mode) | FILE_ATTR
                
                os.chmod(path, mode)
            
            elif os.path.isdir(path):
            
                # Ensure that the remote client doesn't mess up the
                # directory access attributes.
                mode = self.mode | DIR_EXEC
                
                os.chmod(path, mode)
            
            # Construct the new details for the object.
            filetype, date, length, access_attr, object_type, \
                handle = self.read_path_info(path)
            
            return [filetype, date, length, access_attr, object_type], path
        
        except OSError:
        
            return None, path
    
    def rename_path(self, event, reply_id, pos, amount, buf, ros_path,
                    _socket, address, fn):
    
        # Convert the RISC OS style path to a path within the share.
        path = self.from_riscos_path(ros_path)
        
        if ros_path == "":
        
            # The share itself is being referenced.
            return
        
        if path is None: return
        
        # Find whether the directory structure can be legitimately descended.
        path, rest = self.descend_path(path, check_mode = self.write_mask)
        
        if rest != []: return None
        
        if self.present == "truncate":
        
            # Check for a file suffix to determine the filetype of the file.
            # We will need to remember this when we rename the file in order
            # to maintain the correct type.
            at = string.rfind(path, ".")
            
            if at != -1:
            
                suffix = path[at:]
            
            else:
            
                suffix = ""
        
        # Call the function to receive the filename.
        share_name, new_ros_path = fn(
            event, reply_id, pos, amount, buf, _socket, address
            )
        
        if share_name != self.name: return None
        
        if new_ros_path is None: return None
        
        # Convert the RISC OS style path to a path within the share.
        new_path = self.from_riscos_path(new_ros_path, find_obj = 0)
        
        if new_ros_path == "":
        
            # The share itself is being referenced.
            return None
        
        if new_path is None: return None
        
        # Find whether the directory structure can be legitimately descended.
        parent_path, file = os.path.split(new_path)
        
        write_path, rest = self.descend_path(
            parent_path, check_mode = self.write_mask
            )
        
        if rest != []: return None
        
        if self.present == "truncate":
        
            # Append the suffix recorded before to the new path.
            new_path = new_path + suffix
        
        try:
        
            os.rename(path, new_path)
        
        except OSError:
        
            pass
    
    def set_filetype(self, fh, filetype_word, date_word):
    
        # Find the filetype and date from the words given.
        filetype, date = \
            self.take_riscos_filetype_date(filetype_word, date_word)
            
        # Only change the filename to change the filetype if we are using
        # a presentation policy based on truncating filenames before their
        # suffixes.
        
        if os.path.isfile(fh.path) and self.present == "truncate":
        
            # Convert the file's path to a RISC OS style filetype and path.
            discard_filetype, ros_path = self.suffix_to_filetype(fh.path)
            
            # Determine the correct suffix to use for the file.
            new_path = self.filetype_to_suffix(ros_path, filetype)
            
            self.log("comment", "Renaming %s to %s" % (fh.path, new_path), "")
            
            if fh.path != new_path:
            
                try:
                
                    # Try to rename the object.
                    os.rename(fh.path, new_path)
                
                except OSError:
                
                    return None
            
            fh.path = new_path
        
        # Construct the new details for the object.
        filetype, date, length, access_attr, object_type, \
            handle = self.read_path_info(fh.path)
        
        # Keep the length from the original file.
        length = fh.length()
        
        return [filetype, date, length, access_attr, object_type, handle]
    
    def catalogue_path(self, ros_path):
    
        # Convert the RISC OS style path to a path within the share.
        path = self.from_riscos_path(ros_path)
        
        if not os.path.isdir(path):
        
            # The path given did not refer to a directory.
            return None, "Not a directory", path
        
        if path is None:
        
            return None, "Not found", path
        
        # Find whether the directory structure can be legitimately descended.
        path, rest = self.descend_path(path, check_mode = self.read_mask)
        
        if rest != []:
        
            return None, "Access denied", path
        
        try:
        
            # For unprotected shares, return a catalogue to the client.
            files = os.listdir(path)
        
        except OSError:
        
            return None, "Not found", path
        
        # Write the catalogue information.
        
        info = []
        
        # The first word is the length of the directory structure
        # information.
        # Calculate this later.
        info.append(0)
        
        # The next word is the length of the following share
        # information.
        info.append(0x24)
        
        dir_length = 0
        
        n_files = 0
        
        for file in files:
        
            # Omit files which begin with a suffix separator ("." on
            # Linux, for example).
            if string.find(file, os.extsep) == 0:
            
                continue
            
            file_info = []
            length = 0
            
            # Construct the path to the file.
            this_path = os.path.join(path, file)
            
            try:
            
                # Filetype word
                filetype, filename = \
                    self.suffix_to_filetype(file, present = self.present)
                
                # Construct the filetype and date words.
                
                # The number of seconds since the last modification
                # to the file is read.
                seconds = os.stat(this_path)[os.path.stat.ST_MTIME]
                
                # Convert this to the RISC OS date format.
                cs = self.to_riscos_time(seconds = seconds)
                
                filetype_word = \
                    0xfff00000 | (filetype << 8) | \
                    ((cs & 0xff00000000) >> 32)
                
                file_info.append(filetype_word)
                
                length = length + 4
                
                # Date word
                file_info.append(cs & 0xffffffff)
                length = length + 4
                
                # Length word (0x800 for directory)
                if os.path.isdir(this_path):
                
                    file_info.append(ROS_DIR_LENGTH)
                
                else:
                
                    file_info.append(os.path.getsize(this_path))
                
                length = length + 4
                
                # Access attributes (masked by the share's access mask)
                file_info.append(
                    self.to_riscos_access(path = this_path) & self.access_attr
                    )
                
                length = length + 4
                
                # Object type (0x2 for directory)
                if os.path.isdir(this_path):
                
                    file_info.append(0x02)
                
                else:
                
                    file_info.append(0x01)
                
                length = length + 4
                
                # Convert the name into a form suitable for the
                # other client.
                #file_name = self.to_riscos_filename(file)
                
                # Zero terminated name string
                name_string = self._encode([filename + "\x00"])
                
                file_info.append(name_string)
                
                length = length + len(name_string)
                
                n_files = n_files + 1
            
            except OSError:
            
                file_info = []
                length = 0
            
            info = info + file_info
            dir_length = dir_length + length
        
        # The data following the directory structure is concerned
        # with the share and is like a return value from a share
        # open request but with a "B" command word like a
        # catalogue request.
        
        # Use the inode of the directory as its handle.
        handle = os.stat(path)[os.path.stat.ST_INO] & 0xffffffff
        
        share_value = (handle & 0xffffff00) ^ 0xffffff02
        
        trailer = \
        [
            0xffffcd00,  0x00000000, 0x00000800,
            0x00000013, # Read only for others (0x10); read write for owner
            share_value, # common value for directories in this share
            handle, # handle of object as with info returned for opening
            dir_length, # number of words used to describe the directory
                        # contents
            0xffffffff
        ]
        
        # Fill in the directory length.
        info[0] = dir_length
        
        # Return the lists used to construct the message and the path
        # catalogued.
        return info, trailer, path
    
    def send_file(self, fh, pos, length):
    
        # Determine the length of the file.
        file_length = fh.length()
        
        # Determine the amount of information we can send.
        amount = min(length, SEND_GET_SIZE)
        
        # Find the relevant part of the file.
        fh.seek(pos, 0)
        
        # Read the amount of data required.
        file_data = fh.read(amount)
        
        # Calculate the new offset into the file.
        new_pos = pos + len(file_data)
        
        # Write the message header.
        header = [len(file_data), 0xc]
        
        self.log("comment", "Wrote return header: %s" % header, "")
        
        # Encode the header, adding padding if necessary.
        header = self._encode(header)
        
        self.log("comment", "Wrote %i bytes of data" % len(file_data), "")
        
        # Add a 12 byte trailer onto the end of the data
        # containing the amount of data sent and the new
        # offset into the file being read.
        trailer = [len(file_data), new_pos]
        
        self.log("comment", "Wrote return trailer: %s" % trailer, "")
        
        # Encode the trailer, adding padding if necessary.
        trailer = self._encode(trailer)
        
        # Construct the information string.
        info = header + file_data
        
        return info, trailer, new_pos
    
    def create_directory(self, ros_path):
    
        # Construct a path to the object below the shared directory.
        path = self.from_riscos_path(ros_path, find_obj = 0)
        
        if ros_path == "":
        
            # The share itself is being referenced.
            return None, path
        
        # Return if the path could not be translated.
        if path is None:
        
            return None, path
        
        # Determine whether the parent directory of the file can be written
        # to.
        parent_path, file = os.path.split(path)
        
        write_path, rest = self.descend_path(
            parent_path, check_mode = self.write_mask
            )
        
        print write_path, rest
        
        # Return an error value if it can't.
        if rest != []: return None, write_path
        
        try:
        
            # Create a drectory on the local filesystem.
            os.mkdir(path)
        
        except OSError:
        
            return None, path
        
        try:
        
            # Make the directory executable by everyone but retain the
            # other mode attributes for this share.
            os.chmod(path, self.mode | DIR_EXEC)
        
        except OSError:
        
            os.rmdir(path)
            return None, path
        
        self.log("comment", "Actual path: %s" % path, "")
        self.log(
            "comment",
            "%s has permissions: %s" % \
                (path, oct(os.stat(path)[os.path.stat.ST_MODE])),
            ""
            )
        
        # Try to find the details of the directory.
        
        filetype, date, length, access_attr, object_type, \
            handle = self.read_path_info(path)
        
        # Keep this handle for possible later use.
        if not self.file_handler.has_key(handle):
        
            self.file_handler[handle] = Directory(path, self)
        
        return [ filetype, date, length, access_attr, object_type,
                 handle ], path
    
    


class RemoteShare(Ports, Translate):

    def __init__(self, name, host, messages):
    
        Ports.__init__(self)
        Translate.__init__(self)
        
        self.name = name
        self.host = host
        
        # Keep a reference to the messages object passed by the Peer.
        self.share_messages = messages
    
    def _read_file_info(self, data):
    
        # Read the information on the object.
        filetype_word = self.str2num(4, data[4:8])
        filetype = (filetype_word & 0xfff00) >> 8
        date_str = hex(self.str2num(4, data[4:8]))[-2:] + \
                hex(self.str2num(4, data[8:12]))[2:]
        
        date = self.from_riscos_time(long(date_str, 16))
        
        length = self.str2num(4, data[12:16])
        access_attr = self.str2num(4, data[16:20])
        object_type = self.str2num(4, data[20:24])
        
        info = { "filetype": filetype, "date": date,
                 "length": length,
                 "access": access_attr, "type": object_type,
                 "isdir": (object_type == 0x2) }
        
        if len(data) > 24:
        
            handle = self.str2num(4, data[24:28])
            
            info["handle"] = handle
        
        return info
    
    def open(self, ros_path):
    
        """open(self, name)
        
        Open a resource of a given name in the share.
        """
        
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        msg = ["A", 1, 0, name+"\x00"]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return None
        
        else:
        
            print 'Successfully opened "%s"' % name
        
        # Return the information on the item.
        return self._read_file_info(data)
    
    def catalogue(self, ros_path):
    
        """lines = catalogue(self, ros_path)
        
        Return a catalogue of the files in the named share.
        """
        
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        msg = ["B", 3, 0xffffffff, 0, name+"\x00"]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["S"])
        
        if replied != 1:
        
            return
        
        # Read the catalogue information.
        c = 4
        
        # The first word is the length of the directory structure in bytes
        # beginning with the next word.
        dir_length = self.str2num(4, data[c:c+4])
        c = c + 4
        
        start = c
        
        # The next word is the directory name.
        c = c + 4
        
        lines = []
        files = []
        
        while c < (start + dir_length):
        
            # Filetype word
            filetype_word = self.str2num(4, data[c:c+4])
            filetype = (filetype_word & 0xfff00) >> 8
            c = c + 4
            
            # Unknown word
            date_str = hex(filetype_word)[-2:] + \
                hex(self.str2num(4, data[c:c+4]))[2:]
            
            date = self.from_riscos_time(long(date_str, 16))
            
            c = c + 4
            
            # Length word (0x800 for directory)
            length = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Access attributes
            access_attr = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Object type (0x2 for directory)
            object_type = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Zero terminated name string
            name = self.read_string(
                data, offset = c, ending = "\000", include = 0
                )
            
            c = c + len(name) + 1
            
            if c % 4 != 0:
            
                c = c + 4 - (c % 4)
            
            files.append( (
                filetype_word, date, length, access_attr, object_type, name
                ) )
            
            lines.append(
                "%s\t:\t%03x\t(%i bytes)\t%s\t%i\t%s" % (
                    name, filetype, length,
                    self.repr_mode(self.from_riscos_access(access_attr)),
                    object_type,
                    time.asctime(date)
                    )
                )
        
        for line in lines:
        
            print string.expandtabs(line, 4)
        
        # The data following the directory structure is concerned
        # with the share and is like a return value from a share
        # open request but with a "B" command word like a
        # catalogue request.
        
        # Return the catalogue information.
        return files
    
    cat = catalogue
    
    def get(self, name):
    
        # Read the object's information.
        info = self.open(name)
        
        if info is None:
        
            return
        
        # Use the file handle obtained from the information retrieved about
        # this object.
        handle = info["handle"]
        
        file_data = []
        pos = 0
        
        # Request packets smaller than the receive buffer size.
        packet_size = RECV_GET_SIZE
        
        while pos < info["length"]:
        
            msg = ["B", 0xb, handle, pos, packet_size]
            
            # Send the request.
            replied, data = self._send_request(msg, self.host, ["S"])
            
            if replied != 1:
            
                print "The machine containing the shared disc does not respond"
                return
            
            # Read the header.
            length = self.str2num(4, data[4:8])
            trailer_length = self.str2num(4, data[8:12])
            
            file_data.append(data[12:12+length])
            
            #print length, trailer_length, len(data)
            
            pos = pos + length
            
            if len(data[12+length:]) == trailer_length:
            
                returned = self.str2num(4, data[12+length+4:12+length+8])
                new_pos = self.str2num(4, data[12+length+8:12+length+12])
                
                # We have found the packet's trailer.
                sys.stdout.write(
                    "\rRead %i/%i bytes of file %s" % (
                        new_pos, info["length"], name
                        )
                    )
                sys.stdout.flush()
        
        
        # Ensure that the whole file has been read.
        msg = ["B", 0xb, handle, info["length"], 0]
        replied, data = self._send_request(msg, self.host, ["S"])
        
        if replied != 1:
        
            return None
        
        else:
        
            length = self.str2num(4, data[4:8])
            trailer_length = self.str2num(4, data[8:12])
            
            if len(data[12+length:]) == trailer_length:
            
                returned = self.str2num(4, data[12+length+4:12+length+8])
                new_pos = self.str2num(4, data[12+length+8:12+length+12])
                
                # We have found the packet's trailer.
                sys.stdout.write(
                    "\rFile %s (%i bytes) read successfully" % (
                        name, new_pos
                        )
                    )
                sys.stdout.flush()
        
        # Close the resource.
        self._close(handle)
        
        return string.join(file_data, "")
    
    def pget(self, name):
    
        # Read the object's information.
        info = self.open(name)
        
        if info is None:
        
            return
        
        # Use the file handle obtained from the information retrieved about
        # this object.
        handle = info["handle"]
        
        file_data = []
        pos = 0
        
        # Request packets smaller than the receive buffer size.
        packet_size = RECV_GET_SIZE
        
        start_addr = 0
        
        while start_addr < info["length"]:
        
            next_addr = min(start_addr + packet_size, info["length"])
            
            msg = ["A", 0xb, handle, start_addr, next_addr - start_addr]
            
            # Send the request.
            replied, data = self._send_request(msg, self.host, ["D"])
            
            reply_id = data[1:4]
            
            if replied != 1:
            
                print "The machine containing the shared disc does not respond"
                return
            
            from_addr = start_addr
            
            while 1:
            
                # Read the header.
                if data[0] == "D" and len(data) > 8:
                
                    from_addr = self.str2num(4, data[4:8]) + start_addr
                    
                    file_data.append(data[8:])
                    
                    from_addr = from_addr + len(data) - 8
                
                elif data[0] == "D":
                
                    data_pos = self.str2num(4, data[4:8]) + start_addr
                    
                    if data_pos == next_addr:
                    
                        break
                
                elif data[0] == "R" and from_addr == next_addr:
                
                    break
                
                msg = ["r", from_addr - start_addr, next_addr - start_addr]
                
                # Send the request.
                replied, data = self._send_request(
                    msg, self.host, ["D", "R"], new_id = reply_id
                    )
                
                if replied != 1:
                
                    print "The machine containing the shared disc does not respond"
                    return
            
            sys.stdout.write(
                "\rRead %i/%i bytes of file %s" % (
                    from_addr, info["length"], name
                    )
                )
            sys.stdout.flush()
            
            # Increase the start position.
            start_addr = next_addr
        
        sys.stdout.write(
            "\rFile %s (%i bytes) read successfully" % (
                name, info["length"]
                )
            )
        sys.stdout.flush()
        
        # Close the resource.
        self._close(handle)
        
        return string.join(file_data, "")
    
    def _close(self, handle):
    
        #if handle is None:
        #
        #    # Read the object's information.
        #    info = self.open(name, host)
        #    
        #    if info is None:
        #    
        #        return
        #    
        #    # Use the file handle obtained from the information retrieved about
        #    # this object to close the resource.
        #    handle = info["handle"]
        
        msg = ["A", 0xa, handle]
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return None
    
    def put(self, path, ros_path):
    
        # Use the non-broadcast socket.
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return 0, []
        
        s = self.ports[49171]
        
        try:
        
            # Determine the file's relevant filetype and
            # date words.
            filetype_word, date_word = self.make_riscos_filetype_date(path)
            
            # Find the length of the file.
            length = os.path.getsize(path)
            
            # Construct access attributes for the other client.
            access_attr = self.to_riscos_access(path = path)
            
            # Use a default value for the object type.
            object_type = 0x0101
        
        except OSError:
        
            print "Failed to find file: %s" % path
            return
        
        # Convert the filename into a RISC OS filename on the share.
        directory, file = os.path.split(path)
        
        self.log("comment", "File to put: %s" % file, "")
        
        filetype, ros_file = \
            self.suffix_to_filetype(file, present = self.present)
        
        self.log("comment", "Remote file: %s" % ros_file, "")
        
        # Determine whether the share path supplied refers to a file
        # or a directory.
        
        info = self.catalogue(ros_path)
        
        if info is not None:
        
            # A directory
            
            # Prefix the path in the share with the share name and append
            # the filename to obtain a full share path to the object.
            ros_path = ros_path + "." + ros_file
            
            full_path = self.name + "." + ros_path
        
        else:
        
            # A file or no existing object
            
            # Use the share path given and ignore the filename derived
            # from the local path.
            
            full_path = self.name + "." + ros_path
        
        self.log("comment", "Remote path: %s" % ros_path, "")
        
        # Create a file on the remote server using the full path.
        msg = ["A", 0x4, 0, full_path+"\x00"]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return
        
        # The data returned represents the information about the newly
        # created remote file.
        info = self._read_file_info(data)
        
        if info is None or not info.has_key("handle"):
        
            print "Cannot send file to client."
            return
        
        # Send the file, from the start to  its length.
        msg = ["A", 0xc, info["handle"], 0, length]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["w"])
        
        if replied != 1:
        
            # Tidy up.
            self._close(info["handle"])
            
            # Use the share path rather than the full share path as the
            # delete method will prepend the share name.
            self.delete(ros_path)
            return
        
        # A reply containing two words was returned. Presumably, the
        # second is the length of the data to be sent and the first is
        # the position in the file of the data requested (like the
        # get method's "B" ... 0xb message.
        reply_id = data[1:4]
        from_addr = self.str2num(4, data[4:8])
        to_addr = self.str2num(4, data[12:16])
        amount = min(SEND_SIZE, to_addr - from_addr)
        
        try:
        
            f = open(path, "rb")
            
            while from_addr < length:
            
                f.seek(from_addr, 0)
                
                # Send a message with the offset of that data within the
                # file.
                msg = ["d"+reply_id, from_addr]
                
                # Read the data to be sent.
                file_data = f.read(amount)
                
                # Don't pad the data sent.
                msg = self._encode(msg) + file_data
                self.log(
                    "comment",
                    "%i bytes of data sent in message." % len(file_data),
                    ""
                    )
                
                # Send the reply as a string.
                s.sendto(msg, (self.host, 49171))
                
                # Wait for messages to arrive with the same ID as
                # the one used to specify the file to be uploaded.
                replied, data = self._expect_reply(
                    s, msg, self.host, reply_id, ["w", "R"]
                    )
                
                if replied != 1:
                
                    # Tidy up.
                    self._close(info["handle"])
                    
                    # Use the share path rather than the full share path as the
                    # delete method will prepend the share name.
                    self.delete(ros_path)
                    
                    f.close()
                    
                    print "Uploading was terminated."
                    return
                
                #pos = pos + amount
                if data[0] == "w":
                
                    # More data requested.
                    reply_id = data[1:4]
                    from_addr = self.str2num(4, data[4:8])
                    to_addr = self.str2num(4, data[12:16])
                    amount = min(SEND_SIZE, to_addr - from_addr)
                
                elif data[0] == "R":
                
                    from_addr = self.str2num(4, data[4:8])
                    total_length = self.str2num(4, data[8:12])
                    break
                
                sys.stdout.write(
                    "\rWritten %i/%i bytes of file %s" % (
                        from_addr, length, ros_path
                        )
                    )
                sys.stdout.flush()
            
            # Remove all relevant messages from the message list.
            messages = self.messages._all_messages(reply_id, ["w", "R"])
            
            print "Discarded messages."
            for msg in messages:
            
                for line in self.interpret(msg):
                
                    print line
                print
            
            # When all the data has been sent, send an empty "d" message.
            msg = ["d"+reply_id, length]
            
            self._send_list(msg, s, (self.host, 49171))
            
            sys.stdout.write(
                '\rFile "%s" (%i bytes) successfully written to "%s"' % (
                    path, length, ros_path
                    )
                )
            sys.stdout.flush()
        
        except IOError:
        
            # Tidy up.
            self._close(info["handle"])
            
            # Use the share path rather than the full share path as the
            # delete method will prepend the share name.
            self.delete(ros_path)
            
            print "Uploading was terminated."
            return
        
        # Set the filetype and date stamp.
        msg = [ "A", 0x10, info["handle"], filetype_word, date_word ]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            # Tidy up.
            self._close(info["handle"])
            
            # Use the share path rather than the full share path as the
            # delete method will prepend the share name.
            self.delete(ros_path)
            return
        
        # Tidy up.
        self._close(info["handle"])
    
    def pput(self, path, ros_path):
    
        # Use the non-broadcast socket.
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return 0, []
        
        s = self.ports[49171]
        
        try:
        
            # Determine the file's relevant filetype and
            # date words.
            filetype_word, date_word = self.make_riscos_filetype_date(path)
            
            # Find the length of the file.
            length = os.path.getsize(path)
            
            # Construct access attributes for the other client.
            access_attr = self.to_riscos_access(path = path)
            
            # Use a default value for the object type.
            object_type = 0x0101
        
        except OSError:
        
            print "Failed to find file: %s" % path
            return
        
        # Convert the filename into a RISC OS filename on the share.
        directory, file = os.path.split(path)
        
        self.log("comment", "File to put: %s" % file, "")
        
        filetype, ros_file = \
            self.suffix_to_filetype(file, present = self.present)
        
        self.log("comment", "Remote file: %s" % ros_file, "")
        
        # Determine whether the share path supplied refers to a file
        # or a directory.
        
        info = self.catalogue(ros_path)
        
        if info is not None:
        
            # A directory
            
            # Prefix the path in the share with the share name and append
            # the filename to obtain a full share path to the object.
            ros_path = ros_path + "." + ros_file
            
            full_path = self.name + "." + ros_path
        
        else:
        
            # A file or no existing object
            
            # Use the share path given and ignore the filename derived
            # from the local path.
            
            full_path = self.name + "." + ros_path
        
        
        self.log("comment", "Remote path: %s" % ros_path, "")
        
        # Create a file on the remote server using the full share path.
        msg = ["A", 0x4, 0, full_path+"\x00"]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return
        
        # The data returned represents the information about the newly
        # created remote file.
        info = self._read_file_info(data)
        
        if info is None or not info.has_key("handle"):
        
            print "Cannot send file to client."
            return
        
        try:
        
            f = open(path, "rb")
            
            start_addr = 0
            
            while start_addr < length:
            
                # Send the file, from the start to  its length.
                next_addr = min(length, start_addr + SEND_PPUT_SIZE)
                
                # Send the start offset into the file and the amount of data
                # to be transferred.
                msg = [ "A", 0xc, info["handle"], start_addr,
                        next_addr - start_addr ]
                
                # Send the request.
                replied, data = self._send_request(msg, self.host, ["w"])
                
                if replied != 1:
                
                    # Tidy up.
                    self._close(info["handle"])
                    
                    # Use the share path rather than the full share path as the
                    # delete method will prepend the share name.
                    self.delete(ros_path)
                    return
                
                # A reply containing two words was returned. These are the
                # start and end offsets into the file relative to the
                # start offset we gave previously.
                
                from_addr = start_addr
                
                while 1:
                
                    if data[0] == "w":
                    
                        # More data requested.
                        reply_id = data[1:4]
                        
                        # Convert the relative addresses into absolute ones.
                        from_addr = start_addr + self.str2num(4, data[4:8])
                        
                        to_addr = start_addr + \
                            min(self.str2num(4, data[12:16]), next_addr)
                            
                        amount = min(SEND_SIZE, to_addr - from_addr)
                    
                    elif data[0] == "R":
                    
                        # Convert the relative addresses into absolute ones.
                        from_addr = start_addr + self.str2num(4, data[4:8])
                        #total_length = start_addr + self.str2num(4, data[8:12])
                        break
                    
                    f.seek(from_addr, 0)
                    
                    # Send a message with the offset of that data within the
                    # file. The address sent is relative to the start of the
                    # block specified.
                    msg = ["d"+reply_id, from_addr - start_addr]
                    
                    # Read the data to be sent.
                    file_data = f.read(amount)
                    
                    # Don't pad the data sent.
                    msg = self._encode(msg) + file_data
                    self.log(
                        "comment",
                        "%i bytes of data sent in message." % len(file_data),
                        ""
                        )
                    
                    # Send the reply as a string.
                    s.sendto(msg, (self.host, 49171))
                    
                    # Send a message with the amount of data specified.
                    # The address sent is relative to the start of the
                    # block specified.
                    msg = ["d", from_addr - start_addr]
    
                    # Wait for messages to arrive with the same ID as
                    # the one used to specify the file to be uploaded.
                    replied, data = self._send_request(
                        msg, self.host, ["w", "R"], new_id = reply_id
                        )
                    
                    if replied != 1:
                    
                        # Tidy up.
                        self._close(info["handle"])
                        
                        # Use the share path rather than the full share path as the
                        # delete method will prepend the share name.
                        self.delete(ros_path)
                        
                        f.close()
                        
                        print "Uploading was terminated."
                        return
                
                #pos = pos + amount
                sys.stdout.write(
                    "\rWritten %i/%i bytes of file %s" % (
                        from_addr, length, ros_path
                        )
                    )
                sys.stdout.flush()
                
                # Increase the start position.
                start_addr = next_addr
            
            # Remove all relevant messages from the message list.
            messages = self.messages._all_messages(reply_id, ["w", "R"])
            
            print "Discarded messages."
            for msg in messages:
            
                for line in self.interpret(msg):
                
                    print line
                print
            
            # When all the data has been sent, send an empty "d" message.
            msg = ["d"+reply_id, length]
            
            self._send_list(msg, s, (self.host, 49171))
            
            sys.stdout.write(
                '\rFile "%s" (%i bytes) successfully written to "%s"' % (
                    path, length, ros_path
                    )
                )
            sys.stdout.flush()
        
        except IOError:
        
            # Tidy up.
            self._close(info["handle"])
            
            # Use the share path rather than the full share path as the
            # delete method will prepend the share name.
            self.delete(ros_path)
            
            print "Uploading was terminated."
            return
        
        # Set the filetype and date stamp.
        msg = [ "A", 0x10, info["handle"], filetype_word, date_word ]
        
        # Send the request.
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            # Tidy up.
            self._close(info["handle"])
            
            # Use the share path rather than the full share path as the
            # delete method will prepend the share name.
            self.delete(ros_path)
            return
        
        # Tidy up.
        self._close(info["handle"])
    
    def delete(self, ros_path):
    
        """delete(self, ros_path)
        
        Delete the named file on the specified host.
        """
        
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        msg = ["A", 0x6, 0, name + "\x00"]
        
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied == 1:
        
            sys.stdout.write('Deleted "%s" on "%s"' % (name, self.host))
            sys.stdout.flush()
    
    def rename(self, name1, name2):
    
        msg = ["A", 0x9, len(name2), 0, name1 + "\x00"]
        
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return
        
        # The data returned represents the information about the file.
        info = self._read_file_info(data)
        
        
    
    def setmode(self, ros_path, mode):
    
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        access_attr = self.to_riscos_access(mode = mode)
        
        msg = ["A", 0x7, access_attr, 0, name+"\x00"]
        
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return
        
        # Read the information returned.
        info = self._read_file_info(data)
        
        return info
    
    def settype(self, ros_path, filetype):
    
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        # Obtain information on the file (open it).
        info = self.open(name)
        
        cs = self.to_riscos_time(ttuple = info["date"])
        
        filetype_word, date_word = \
            self._make_riscos_filetype_date(filetype, cs)
        
        msg = ["A", 0x10, info["handle"], filetype_word, date_word]
        
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return
        
        self._close(info["handle"])
    
    def create_directory(self, ros_path):
    
        """create_directory(self, ros_path)
        
        Create a directory at a location within the share.
        """
        
        name = self.name
        
        if ros_path != "":
        
            name = name + "." + ros_path
        
        msg = ["A", 0x5, 0, name + "\x00"]
        
        replied, data = self._send_request(msg, self.host, ["R"])
        
        if replied != 1:
        
            return None
        
        sys.stdout.write('Created "%s" on share "%s"' % (name, self.host))
        sys.stdout.flush()
        
        # Read the information returned.
        info = self._read_file_info(data)
        
        return info



class Peer(Ports):

    def __init__(self, debug = 1):
    
        # Call the initialisation method of the base classes.
        Ports.__init__(self)
        
        self.debug = 1
        # ---------------------------------------------------------------------
        # Socket configuration
        
        self.identity = self.number(4, id(self))
        
        # ---------------------------------------------------------------------
        # Thread configuration
        
        # Create an event to use to terminate the polling thread.
        self.poll_event = threading.Event()
        
        # Create a thread to call the broadcast_poll method of the
        # access object.
        self.poll_thread = threading.Thread(
            group = None, target = self.broadcast_poll,
            name = "Poller", args = (self.poll_event,)
            )
        
        # Create an event to use to inform the listening thread that it
        # must terminate.
        self.listen_event = threading.Event()
        
        # Create a thread to use to listen for packets sent directly to
        # our machine.
        self.listen_thread = threading.Thread(
            group = None, target = self.listen,
            name = "Listener", args = (self.listen_event,)
            )
        
        # ---------------------------------------------------------------------
        # Resources configuration
        
        self._log = []
        
        # Maintain a dictionary of known clients, shares and printers.
        # Each of these will use a separate thread.
        self.clients = {}
        self.shares = {}
        self.printers = {}
        self.transfers = {}
        
        # Keep a dictionary of events to use to communicate with threads.
        self.printer_events = {}
        self.transfer_events = {}
        
        # Create lists of messages sent to each listening socket.
        
        # General messages.
        self.general_messages = Messages()
        
        # Messages about shares.
        self.share_messages = Messages()
        
        # Use an object to manage the file handles used by shares owned by
        # this Peer.
        self.file_handler = Files()
        
        # Maintain a dictionary of open shares, on the local host or
        # on other hosts.
        # Each entry in this dictionary is referenced by a tuple containing
        # the name of the share and the host it resides on and contains the
        # ID value used to open it.
        self.open_shares = {}
        
        # Start serving.
        self.serve()
        
        # Read the share configuration file, creating shares as required.
        self.create_shares()
    
    def __del__(self):
    
        # Stop any serving threads.
        self.stop()
        
        # Close all sockets.
        for port, _socket in self.broadcasters.items():
        
            print "Closing socket for port %i" % port
            _socket.close()
        
        for port, _socket in self.ports.items():
        
            print "Closing socket for port %i" % port
            _socket.close()
    
    def create_shares(self):
    
        # Compile a list of paths to check for the access.cfg file.
        
        # Start with the current directory.
        paths = [""]
        
        # Look for a file in the path used to invoke this program.
        path, file = os.path.split(sys.argv[0])
        paths.append(path)
        
        # Add the user's home directory.
        paths.append(os.getenv("HOME"))
        
        f = None
        
        for path in paths:
        
            try:
            
                f = open(os.path.join(path, ".access"), "r")
                break
            
            except IOError:
            
                # Loop again.
                pass
        
        if f is None:
        
            print "Failed to find access.cfg file."
            lines = []
        
        else:
        
            lines = f.readlines()
            f.close()
        
        # Read the lines found.
        for line in lines:
        
            # Strip leading and trailing whitespace.
            s = string.strip(line)
            
            values = []
            current = ""
            
            # Ignore lines beginning with a "#" character.
            if s[:1] == "#": continue
            
            for c in s:
            
                if c not in string.whitespace:
                
                    current = current + c
                
                elif current != "":
                
                    values.append(current)
                    current = ""
            
            if current != "":
            
                values.append(current)
            
            # The values correspond to various fields corresponding to the
            # following syntax:
            #
            # <share> <path> <mode> <delay> <translation> <filetype>
            #
            # The "share" parameter is the name by which other clients
            # refer to the contents of the shared directory.
            #
            # The "path" is the path on the local filesystem which can be
            # navigated by other clients.
            #
            # The "mode" is an octal value describing a mask to apply to
            # the files and directories in the shared directory. This
            # is loosely translated into a value for the protected flag
            # which is understood by RISC OS clients.
            #
            # The "delay" parameter sets the delay between availability
            # broadcasts on the network. This can be disabled by supplying
            # the value "off" (without quotes) or set to the default value
            # using the value "default".
            #
            # The "translation" parameter is either "suffix" or "truncate"
            # indicating that filename suffixes are either to be presented
            # to other clients or truncated.
            #
            # A final parameter is the default filetype to be used for
            # files whose type cannot be determined using the MimeMap
            # file. This should take the form of a twelve bit integer in
            # Python or C hexadecimal form, e.g. 0xfff.
            #
            # myshare /home/user/myfile 0644 off truncate 0xffd
            
            if len(values) == 6:
            
                # Try to create this share.
                name, path, mode, delay, present, filetype = values[0:6]
                
                try:
                
                    self.add_share(name, path, mode, delay, present, filetype)
                
                except ShareError:
                
                    sys.stderr.write("Could not add share: %s\n" % name)
                    sys.stderr.flush()
                
            elif len(values) > 0:
            
                sys.stderr.write(
                    "Bad or incomplete share description: %s\n" % line
                    )
    
    def read_share_path(self, _string):
    
        path = self.read_string(
            _string, ending = "\x00", include = 0
            )
        
        # Split the path up into elements.
        path_elements = string.split(path, ".")
        
        # The first element is the share name.
        share_name = path_elements[0]
        
        return share_name, string.join(path_elements[1:], ".")
    
    def broadcast_startup(self):
    
        """broadcast_startup(self)
        
        Broadcast startup/availability messages on port 32770.
        """
        
        if not self.broadcasters.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.broadcasters[32770]
        
        # Create the first message to send.
        data = [0x00010001, 0x00000000]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
        
        # Create the second message to send.
        data = [0x00050001, 0x00000000]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
        
        # Create the host broadcast string.
        data = \
        [
            0x00050002, 0x00010000,
            (len(self.identity) << 16) | len(Hostname),
            Hostname + self.identity
        ]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
    
    def broadcast_poll(self, event, delay = 30):
    
        """broadcast_poll(self)
        
        Broadcast a poll on port 32770 every few seconds. Never exits.
        """
        
        if not self.broadcasters.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.broadcasters[32770]
        
        # Create a string to send.
        data = \
        [
            0x00050004, 0x00010000,
            (len(self.identity) << 16) | len(Hostname),
            Hostname + self.identity
        ]
        
        while 1:
        
            self._send_list(data, s, (Broadcast_addr, 32770))
            
            t0 = time.time()
            
            while (time.time() - t0) < delay:
            
                if event.isSet(): return
        
        # Create a string to send.
        data = \
        [
            0x00050003, 0x00010000,
            (len(self.identity) << 16) | len(Hostname),
            Hostname + self.identity
        ]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
    
    def broadcast_printer(self, name, description, event,
                          protected = 0, delay = 30):
    
        """broadcast_share(self, name, description, event,
                           protected = 0, delay = 30)
        
        Broadcast the availability of a printer every few seconds.
        """
        
        # Broadcast the availability of the printer on the polling socket.
        
        if not self.broadcasters.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00020002, 0x00010000,
            (len(description) << 16) | len(name),
            name + description
        ]
        
        self._send_list(data, s, (Broadcast_addr, 32770))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        while 1:
        
            self._send_list(data, s, (Broadcast_addr, 49171))
            
            t0 = time.time()
            
            while (time.time() - t0) < delay:
            
                if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010003, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
    
    def broadcast_directory_share(self, name, event, protected = 0, delay = 30):
    
        """broadcast_share(self, name, event, protected = 0, delay = 30)
        
        Broadcast the availability of a share every few seconds.
        """
        
        # Broadcast the availability of the share on the polling socket.
        
        if not self.broadcasters.has_key(32771):
        
            print "No socket to use for port %i" % 32771
            return
        
        s = self.broadcasters[32771]
        
        data = \
        [
            0x00010002, 0x00010001, 0x00000000
        ]
        
        self._send_list(data, s, (Broadcast_addr, 32771))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        # Broadcast a notification to other clients.
        
        for i in range(0, 5):
        
            self._send_list(data, s, (Broadcast_addr, 49171))
            
            time.sleep(1)
        
        while 1:
        
            self._send_list(data, s, (Broadcast_addr, 32770))
            
            time.sleep(delay)
            
            if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.broadcasters[32771]
        
        data = \
        [
            0x00010003, 0x00010001, 0x00000000
        ]
    
    def send_query(self, host):
    
        if not self.broadcasters.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.broadcasters[32770]
        
        # Create a string to send.
        data = \
        [
            0x00050003, 0x00010000,
            (len(self.identity) << 16) | len(Hostname),
            Hostname + self.identity
        ]
        
        self._send_list(data, s, (host, 32770))
        
        self.read_port([32770, 32771, 49171])
    
    # Method used in thread for transferring files
    
    def receive_file(self, event, reply_id, start, amount, fh, _socket,
                      address):
    
        # This method should only get called once by the thread it belongs
        # to, then the thread should terminate.
        
        pos = start
        
        end = start + amount
        
        #self.log("comment", "Position: %i" % pos, "")
        #self.log("comment", "Expected amount of data: %i" % amount, "")
        #self.log("comment", "End at: %i" % end, "")
        
        # Read the host name from the address tuple.
        host = address[0]
        
        try:
        
            while 1:
            
                # Set the size of packets we can deal with.
                # Note that the length parameter passed is the buffer size the remote
                # client expects. However, we request packets which are small
                # enough for our receive buffer.
                packet_size = min(RECV_PUT_SIZE, end - pos)
                
                # Construct a list to send to the remote client.
                #msg = ["w", pos, 0, pos + packet_size]
                
                # Addresses within the file for the other client to use
                # are relative to the start address it passed to us.
                msg = ["w", pos - start, 0, pos + packet_size - start]
                
                #self.log("comment", repr(msg), "")
                
                # Send the request.
                replied, data = self._send_request(
                    msg, host, ["d"], new_id = reply_id
                    )
                
                if replied == -1:
                
                    raise IOError
                
                elif replied == 1:
                
                    # Read the header.
                    
                    # We must translate the address passed to us back into
                    # an absolute form.
                    
                    if len(data) > 8:
                    
                        # Read the position in the file given by the other
                        # client.
                        data_pos = self.str2num(4, data[4:8]) + start
                        
                        #self.log(
                        #    "comment",
                        #    "Data position (%x) file position (%x)" % (data_pos, pos), ""
                        #    )
                        
                        file_data = data[8:]
                        
                        fh.seek(data_pos, 0)
                        
                        #self.log("comment", file_data, "")
                        
                        #self.log("comment", "File position: %i" % data_pos, "")
                        
                        fh.write(file_data)
                        pos = data_pos + len(file_data)
                        
                        #self.log(
                        #    "comment",
                        #    "Read a total of %i bytes of file %s" % (pos, fh.path), ""
                        #    )
                    
                    else:
                    
                        # Read the amount of data sent in the previous message.
                        data_pos = self.str2num(4, data[4:8]) + start
                        
                        if pos >= end:
                        
                            # A short block was received which indicates
                            # that all the data was read.
                            #self.log(
                            #    "comment",
                            #    "Short block encountered at end of data.", ""
                            #    )
                            break
                
                else:
                
                    # No response. Check the position within the data
                    # received.
                    if pos >= end:
                    
                        break
                    
                    else:
                    
                        raise IOError
                
                # Check the event flag.
                if event.isSet():
                
                    fh.close()
                    break
            
            # Send a reply message to indicate that the transfer has finished.
            msg = ["R"+reply_id, start, pos]
            self._send_list(msg, _socket, address)
        
        except IOError:
        
            pass
        
        # Remove all relevant messages from the message list.
        messages = self.share_messages._all_messages(reply_id, ["d"])
        
        #self.log("comment", "Discarded messages:", "")
        #for msg in messages:
        #
        #    for line in self.interpret(msg):
        #    
        #        self.log("comment", line, "")
        #    
        #    self.log("comment", "", "")
    
    def send_file(self, event, reply_id, code, handle, start, length, fh,
                  _socket, address):
    
        # This method should only get called once by the thread it belongs
        # to, then the thread should terminate.
        
        pos = start
        
        # Determine the amount of information we can send.
        amount = min(length, SEND_GET_SIZE)
        
        end = start + length
        
        self.log("comment", "Position: %i" % pos, "")
        self.log("comment", "Expected amount of data: %i" % amount, "")
        self.log("comment", "End at: %i" % end, "")
        
        # Read the host name from the address tuple.
        host = address[0]
        
        try:
        
            while 1:
            
                # Find the relevant part of the file.
                fh.seek(pos, 0)
                
                # Read the amount of data required.
                file_data = fh.read(amount)
                
                # Calculate the new offset into the file.
                new_pos = pos + len(file_data)
                
                # Send the data prefixed by its offset relative to the
                # start address within the file supplied.
                msg = self._encode(["D"+reply_id, pos - start]) + file_data
                
                self.log(
                    "comment",
                    "Sent %i bytes of data (from %x) to %s" % (
                        len(file_data), pos - start, host
                        ), ""
                    )
                
                self.ports[49171].sendto(msg, (host, 49171))
                
                # Send a message with the new offset within the block
                # requested.
                msg = ["D", new_pos]
                
                # Send the reply.
                replied, data = self._send_request(
                    msg, host, ["r"], new_id = reply_id
                    )
                
                if replied == -1:
                
                    return
                
                elif replied == 1:
                
                    # Read the header.
                    pos = start + self.str2num(4, data[4:8])
                    amount = min(end - pos, SEND_GET_SIZE)
                    
                    if pos >= end:
                    
                        break
                
                else:
                
                    # No response. Check the position within the data
                    # received.
                    if pos >= end:
                    
                        break
                    
                    else:
                    
                        raise IOError
        
            # Send an message indicating that all the data has been sent.
            # We use the code and handle sent to us by the remote client.
            msg = ["R"+reply_id, end - start, end - start]
            
            self._send_list(msg, self.ports[49171], (host, 49171))
        
        except IOError:
        
            msg = ["E"+reply_id, 0x100d6, "Not found"]
            
            # Send a reply.
            self._send_list(msg, _socket, address)
        
        # Remove all relevant messages from the message list.
        messages = self.share_messages._all_messages(reply_id, ["r"])
        
        self.log("comment", "Discarded messages:", "")
        for msg in messages:
        
            for line in self.interpret(msg):
            
                self.log("comment", line, "")
            
            self.log("comment", "", "")
    
    def rename_path(self, event, reply_id, pos, amount, buf,
                    _socket, address):
    
        # Call the function to receive the filename.
        self.receive_file(event, reply_id, pos, amount, buf, _socket, address)
        
        # We should now have the replacement file in the Buffer object
        # passed by the caller.
        value = buf.read()
        
        cleaned = ""
        
        for c in value:
        
            if ord(c) > 31: cleaned = cleaned + c
        
        # Extract the share name and share path from the new path.
        share_name, new_ros_path = self.read_share_path(cleaned)
        
        return share_name, new_ros_path
    
    def read_poll_socket(self):
    
        # Read the listening socket first.
        try:
        
            s = self.ports[32770]
            data, address = s.recvfrom(RECV_SIZE)
            
            self._read_poll_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[32770]
            data, address = s.recvfrom(RECV_SIZE)
            
            self._read_poll_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
    
    def _read_poll_socket(self, data, address):
    
        host = address[0]
        
        # Check the first word of the response to determine what the
        # information is about.
        about = self.str2num(4, data[:4]) 
        
        major = (about & 0xffff0000) >> 16
        minor = about & 0xffff
        
        # The second word of the response is the type of share.
        share_type = self.str2num(4, data[4:8])
        
        if share_type != 0:
        
            # The third word contains two half-word length values.
            length1 = self.str2num(2, data[8:10])
            length2 = self.str2num(2, data[10:12])
        
        # Type 1 (Discs)
        
        if major == 0x0001:
        
            # A share
            
            if minor == 0x0001:
            
                # Startup
                #print "Starting up shares"
                pass
            
            elif minor == 0x0002:
            
                # Share made available
                
                if share_type == 0x00010000:
                
                    # A string follows the leading three words.
                    share_name = data[12:12+length1]
                    
                    c = 12 + length1
                    
                    # The protected flag follows the last byte in the string.
                    protected = self.str2num(length2, data[c:c+length2])
                    
                    if protected not in [0, 1]: protected = 0
                    
                    #print 'Share "%s" (%s) available' % \
                    #    (share_name, ["unprotected", "protected"][protected])
                    
                    # Compare the share with those recorded.
                    
                    if not self.shares.has_key((share_name, host)):
                    
                        # Add the share share_name and host to the shares
                        # dictionary.
                        share = RemoteShare(
                            share_name, host, messages = self.share_messages
                            )
                        
                        self.shares[(share_name, host)] = share
                
                elif share_type == 0x00010001:
                
                    # A directory share
                    
                    pass
            
            elif minor == 0x0003:
            
                # Share withdrawn
                
                # A string follows the leading three words.
                share_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The protected flag follows the last byte in the string.
                protected = self.str2num(length2, data[c:c+length2])
                
                if protected not in [0, 1]: protected = 0
                
                #print 'Share "%s" (%s) withdrawn' % \
                #    (share_name, ["unprotected", "protected"][protected])
                
                # Compare the share with those recorded.
                
                if self.shares.has_key((share_name, host)):
                
                    # Remove the share share_name and host from the shares
                    # dictionary.
                    del self.shares[(share_name, host)]
            
            elif minor == 0x0004:
            
                # Share periodic broadcast
                
                # A string follows the leading three words.
                share_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The protected flag follows the last byte in the string.
                protected = self.str2num(length2, data[c:c+length2])
                
                if protected not in [0, 1]: protected = 0
                
                #print 'Share "%s" (%s)' % \
                #    (share_name, ["unprotected", "protected"][protected])
                
                # Compare the share with those recorded.
                
                if not self.shares.has_key((share_name, host)):
                
                    # Add the share name and host to the shares dictionary.
                    share = RemoteShare(
                        share_name, host, messages = self.share_messages
                        )
                    
                    self.shares[(share_name, host)] = share
            
            else:
            
                print "From: %s:%i" % address
                
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        
        # Type 2 (Printers)
        
        elif major == 0x0002:
        
            # A remote printer
            
            if minor == 0x0002:
            
                # Printer made available
                
                # A string follows the leading three words.
                printer_name = data[12:12+length1]
                
                c = 12 + length1
                
                printer_desc = data[c:c+length2]
                
                c = c + length2
                
                print 'Printer "%s" (%s) available' % \
                    (printer_name, printer_desc)
                
                # Compare the printer with those recorded.
                
                if not self.printer.has_key((name, host)):
                
                    # Add the printer name and host to the printers dictionary.
                    self.printers[(name, host)] = (None, None)
            
            elif minor == 0x0003:
            
                # Printer withdrawn
                
                # A string follows the leading three words.
                printer_name = data[12:12+length1]
                
                c = 12 + length1
                
                printer_desc = data[c:c+length2]
                
                c = c + length2
                
                print 'Printer "%s" (%s) withdrawn' % \
                    (printer_name, printer_desc)
                
                # Compare the printer with those recorded.
                
                if self.printers.has_key((name, host)):
                
                    # Remove the printer name and host from the printers
                    # dictionary.
                    del self.printers[(name, host)]
            
            elif minor == 0x0004:
            
                # Printer periodic broadcast
                
                # A string follows the leading three words.
                printer_name = data[12:12+length1]
                
                c = 12 + length1
                
                printer_desc = data[c:c+length2]
                
                c = c + length2
                
                print 'Printer "%s" (%s)' % \
                    (printer_name, printer_desc)
            
            else:
            
                print "From: %s:%i" % address
                
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        
        # Type 5 (Hosts)
        
        elif major == 0x0005:
        
            # A client
            
            if minor == 0x0001:
            
                # Startup
                #print "Starting up client"
                pass
            
            elif minor == 0x0002:
            
                # Startup broadcast
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                #print "Startup client: %s %s" % (client_name, info)
            
            elif minor == 0x0003:
            
                # Query message (direct)
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                print "Query: %s %08x" % (client_name, self.str2num(4, info))
            
            elif minor == 0x0004:
            
                # Availability broadcast
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                #print "Client available: %s %s" % (client_name, info)
                
                # Compare the client with those in the clients dictionary.
                
                if not self.clients.has_key((client_name, host)):
                
                    # Add an entry for the client to the dictionary.
                    self.clients[(client_name, host)] = info
            
            else:
            
                print "From: %s:%i" % address
                
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        else:
        
            print "From: %s:%i" % address
            
            lines = self.interpret(data)
            
            for line in lines:
            
                print line
    
    def read_listener_socket(self):
    
        # Read the listening socket first.
        try:
        
            s = self.ports[32771]
            data, address = s.recvfrom(RECV_SIZE)
            
            self._read_listener_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[32771]
            data, address = s.recvfrom(RECV_SIZE)
            
            self._read_listener_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
    
    def _read_listener_socket(self, data, address):
    
        print "From: %s:%i" % address
        
        host = address[0]
        
        lines = self.interpret(data)
        
        for line in lines:
        
            print line
        
        print
    
    def read_share_socket(self):
    
        # Read the listening socket first.
        try:
        
            s = self.ports[49171]
            data, address = s.recvfrom(RECV_SIZE)
            
            self.log("comment", "Listening socket", "")
            self._read_share_socket(s, data, address)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[49171]
            data, address = s.recvfrom(RECV_SIZE)
            
            self.log("comment", "Broadcasting socket", "")
            self._read_share_socket(s, data, address)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
    
    def _read_share_socket(self, _socket, data, address):
    
        host = address[0]
        
        #print "From: %s:%i" % address
        #
        #lines = self.interpret(data)
        #
        #for line in lines:
        #
        #    print line
        #
        #print
        
        self.log("received", data, address)
        
        command = data[0]
        reply_id = data[1:4]
        
        if len(data) > 4:
        
            field_max = min(8, len(data))
            code = self.str2num(field_max - 4, data[4:field_max])
        
        else:
        
            code = None
        
        msg = None
        
        if command == "A":
        
            if code == 0x1:
            
                # Open a share, directory or path.
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[12:])
                
                self.log(
                    "comment", 'Request to open "%s" in share "%s"' % (
                        ros_path, share_name
                        ), ""
                    )
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.open_path(ros_path)
                
                except KeyError:
                
                    info = None
                
                if info is not None:
                
                    msg = ["R"+reply_id] + info
                
                elif ros_path == "":
                
                    # Reply with an error message.
                    self._send_list(
                        ["E"+reply_id, 0x163ac, "Shared disc not available."],
                        _socket, address
                        )
                
                else:
                
                    # Reply with an error message.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # For unprotected shares, reply with details of the share.
                
                # Use the first word given but substitute "R" for "A".
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0x2:
            
                # Open a share, directory or path.
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[12:])
                
                self.log(
                    "comment", 'Request to open "%s" in share "%s"' % (
                        ros_path, share_name
                        ), ""
                    )
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.open_path(ros_path)
                
                except KeyError:
                
                    info = None
                
                if info is not None:
                
                    msg = ["R"+reply_id] + info
                
                elif ros_path == "":
                
                    # Reply with an error message.
                    self._send_list(
                        ["E"+reply_id, 0x163ac, "Shared disc not available."],
                        _socket, address
                        )
                
                else:
                
                    # Reply with an error message.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0x4:
            
                # Create and open a share, directory or path.
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[12:])
                
                self.log(
                    "comment", 'Request to create "%s" in share "%s"' % (
                        ros_path, share_name
                        ), ""
                    )
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.create_file(ros_path)
                
                except KeyError:
                
                    info = None
                
                if info is not None:
                
                    msg = ["R"+reply_id] + info
                
                elif ros_path == "":
                
                    msg = \
                    [
                        "E"+reply_id, 0xaf,
                        "'%s' cannot be created - " % path + \
                        "a directory with that name already exists"
                    ]
                
                else:
                
                    # Reply with an error message.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
        
            elif code == 0x5:
            
                # Create and open a share or directory.
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[12:])
                
                self.log(
                    "comment", 'Request to create "%s" in share "%s"' % (
                        ros_path, share_name
                        ), ""
                    )
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.create_directory(ros_path)
                
                except KeyError:
                
                    info = None
                
                if info is not None:
                
                    msg = ["R"+reply_id] + info
                
                elif ros_path == "":
                
                    msg = \
                    [
                        "E"+reply_id, 0xaf,
                        "'%s' cannot be created - " % path + \
                        "a directory with that name already exists"
                    ]
                
                else:
                
                    # Reply with an error message.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
        
            elif code == 0x6:
            
                # Delete request.
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[12:])
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.delete_path(ros_path)
                    
                    if info is not None:
                    
                        msg = [ "R"+reply_id ] + info
                    
                    else:
                    
                        msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                except KeyError:
                
                    msg = ["E"+reply_id, 0x163ac, "Shared disc not available."]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0x7:
            
                # Set access attributes
                
                access_attr = self.str2num(4, data[8:12])
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[16:])
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    info, path = share.set_access_attr(ros_path, access_attr)
                    
                    if info is not None:
                    
                        # Construct a reply.
                        msg = ["R"+reply_id] + info
                    
                    else:
                    
                        msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                except KeyError:
                
                    msg = ["E"+reply_id, 0x163ac, "Shared disc not available."]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0x9:
            
                # Rename file on our machine.
                amount = self.str2num(4, data[8:12])
                
                # Find the share and RISC OS path within it.
                share_name, ros_path = self.read_share_path(data[16:])
                
                try:
                
                    share = self.shares[(share_name, Hostaddr)]
                    
                    # Extract the host name from the address as it is assumed that
                    # communication will be through port 49171.
                    host = address[0]
                    
                    # Start a new thread to request and handle the incoming data.
                    
                    # Create a lock to prevent multiple threads working on the
                    # same file at the same time.
                    if self.transfers.has_key(ros_path):
                    
                        thread, host = self.transfers[ros_path]
                        
                        while thread.isAlive():
                        
                            pass
                    
                    # Create an event to use to inform the thread that it terminate.
                    event = threading.Event()
                    
                    # Record the event in the transfer events dictionary.
                    self.transfer_events[ros_path] = event
                    
                    # Create a buffer to put the filename in.
                    buf = Buffer()
                    
                    # Create a thread to receive the replacement filename,
                    # passing the necessary information to do this.
                    thread = threading.Thread(
                        group = None, target = share.rename_path,
                        name = 'Rename request "%s" from %s:%i' % (
                            ros_path, address[0], address[1]
                            ),
                        args = (
                            event, reply_id, 0, amount, buf, ros_path,
                            _socket, address, self.rename_path
                            )
                        )
                    
                    # Record the thread in the transfers dictionary.
                    self.transfers[ros_path] = thread, host
                    
                    # Start the thread.
                    thread.start()
                
                except KeyError:
                
                    msg = ["E"+reply_id, 0x163ac, "Shared disc not available."]
                    
                    # Send a reply.
                    self._send_list(msg, _socket, address)
            
            elif code == 0xa:
            
                # Close file.
                
                handle = self.str2num(4, data[8:12])
                
                # If the handle is in use then remove it from the handle
                # dictionary.
                try:
                
                    fh = self.file_handler[handle]
                    
                    fh.close()
                    
                    del self.file_handler[handle]
                    
                    # Reply with an short message.
                    msg = ["R"+reply_id]
                
                except KeyError:
                
                    # Ideally, reply with an error message about the file handle
                    # used.
                    msg = ["R"+reply_id]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0xb:
            
                # Send file (data request)
                
                handle = self.str2num(4, data[8:12])
                pos = self.str2num(4, data[12:16])
                length = self.str2num(4, data[16:20])
                
                #print "Data request", hex(handle), pos, length
                
                # Extract the host name from the address as it is assumed that
                # communication will be through port 49171.
                host = address[0]
                
                try:
                
                    fh = self.file_handler[handle]
                    
                    path = fh.path
                    
                    # Start a new thread to request and handle the incoming data.
                    
                    # Create a lock to prevent multiple threads working on the
                    # same file at the same time.
                    if self.transfers.has_key(path):
                    
                        thread, host = self.transfers[path]
                        
                        while thread.isAlive():
                        
                            pass
                    
                    # Create an event to use to inform the thread that it terminate.
                    event = threading.Event()
                    
                    # Record the event in the transfer events dictionary.
                    self.transfer_events[path] = event
                    
                    # Create a thread to send the file.
                    thread = threading.Thread(
                        group = None, target = self.send_file,
                        name = 'Transfer "%s" to %s:%i' % (
                            path, address[0], address[1]
                            ),
                        args = (
                            event, reply_id, code, handle, pos, length, fh,
                            _socket, address
                            )
                        )
                    
                    # Record the thread in the transfers dictionary.
                    self.transfers[path] = thread, host
                    
                    # Start the thread.
                    thread.start()
                
                except KeyError:
                
                    # Reply with an error message.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                    
                    # Send a reply.
                    self._send_list(msg, _socket, address)
            
            elif code == 0xc:
            
                # Receive file
                
                # The remote client has passed the handle, some word
                # and the length of the file.
                handle = self.str2num(4, data[8:12])
                pos = self.str2num(4, data[12:16])
                amount = self.str2num(4, data[16:20])
                
                # Translate the handle into a path.
                fh = self.file_handler[handle]
                
                path = fh.path
                length = fh.length()
                
                self.log("comment", "", "")
                self.log("comment", path, "")
                self.log("comment", "Length of file: %i" % length, "")
                
                # Extract the host name from the address as it is assumed that
                # communication will be through port 49171.
                host = address[0]
                
                # Start a new thread to request and handle the incoming data.
                
                # Create a lock to prevent multiple threads working on the
                # same file at the same time.
                if self.transfers.has_key(path):
                
                    thread, host = self.transfers[path]
                    
                    while thread.isAlive():
                    
                        pass
                
                # Create an event to use to inform the thread that it terminate.
                event = threading.Event()
                
                # Record the event in the transfer events dictionary.
                self.transfer_events[path] = event
                
                # Create a thread to receive the file.
                thread = threading.Thread(
                    group = None, target = self.receive_file,
                    name = 'Transfer "%s" from %s:%i' % (
                        path, address[0], address[1]
                        ),
                    args = (
                        event, reply_id, pos, amount, fh,
                        _socket, address
                        )
                    )
                
                # Record the thread in the transfers dictionary.
                self.transfers[path] = thread, host
                
                # Start the thread.
                thread.start()
                
                # Also notify the other client that the share has been updated.
                
            #elif code == 0xe:
            #
            #    # Set length of file.
            #    handle = self.str2num(4, data[8:12])
            #    length = self.str2num(4, data[12:16])
            #    
            #    msg = ["D"+reply_id, 0]
            #    self._send_list(msg, _socket, address)
            #    
            #    msg = ["R"+reply_id, 0x1234]
            #    self._send_list(msg, _socket, address)
            
            elif code == 0xe or code == 0xf:
            
                # Set length of file.
                
                handle = self.str2num(4, data[8:12])
                new_length = self.str2num(4, data[12:16])
                
                try:
                
                    # Find the path and previously recorded file length.
                    fh = self.file_handler[handle]
                    
                    # Find the current file length.
                    length = fh.length()
                    
                    self.log(
                        "comment",
                        "Change length from %i to %i" % (length, new_length), ""
                        )
                    
                    # If the length is to be changed then open the file for
                    # changing.
                    if length != new_length:
                    
                        fh.set_length(new_length)
                    
                    msg = ["R"+reply_id, new_length]
                
                except IOError:
                
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                except KeyError:
                
                    # We should probably complain about the file handle
                    # rather than about the path.
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
            
            elif code == 0x10:
            
                # Set the file type of a file on our machine.
                
                handle = self.str2num(4, data[8:12])
                filetype_word = self.str2num(4, data[12:16])
                date_word = self.str2num(4, data[16:20])
                
                try:
                
                    # Read the file handle of the file on our machine.
                    fh = self.file_handler[handle]
                    
                    # Use the policy of the share in which the file resides
                    # to modify the file's attributes.
                    share = fh.share
                    
                    del self.file_handler[handle]
                    
                    info = share.set_filetype(fh, filetype_word, date_word)
                    
                    if info is not None:
                    
                        handle = info[-1]
                        
                        # Transfer the file handle to the file on the new path.
                        self.file_handler[handle] = fh
                        
                        # Construct a reply.
                        msg = [ "R"+reply_id ] + info
                    
                    else:
                    
                        msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                except KeyError:
                
                    msg = ["E"+reply_id, 0x100d6, "Not found"]
                
                # Send a reply.
                self._send_list(msg, _socket, address)
        
        elif command == "B" and code == 0x3:
        
            # Request for information.
            
            share_name, ros_path = self.read_share_path(data[16:])
            
            try:
            
                # Read the directory name associated with this share.
                share = self.shares[(share_name, Hostaddr)]
                info, trailer, path = share.catalogue_path(ros_path)
                
                if info is not None:
                
                    # Write the message, starting with the code and ID word.
                    msg = ["S"+reply_id] + info + ["B"+reply_id] + trailer
                    
                    # Send the reply.
                    self._send_list(msg, _socket, address)
                    
                    #print
                    #print "Sent:"
                    #for line in self.interpret(self._encode(msg)):
                    #
                    #    print line
                    #print
                
                elif trailer == "Not a directory":
                
                    # Reply with an error message.
                    self._send_list(
                        ["E"+reply_id, 0x163c5, "Not a Directory"],
                        _socket, address
                        )
                
                elif trailer == "Not found":
                
                    # Reply with an error message.
                    self._send_list(
                        ["E"+reply_id, 0x100d6, "Not found"],
                        _socket, address
                        )
                
                else:
                
                    # Reply with an error message.
                    self._send_list(
                        ["E"+reply_id, 0x100d6, "Not found"],
                        _socket, address
                        )
            
            except KeyError:
            
                # Reply with an error message.
                self._send_list(
                    ["E"+reply_id, 0x163ac, "Shared disc not available."],
                    _socket, address
                    )
        
        elif command == "B" and code == 0xb:
        
            # Data request ("B")
            
            handle = self.str2num(4, data[8:12])
            pos = self.str2num(4, data[12:16])
            length = self.str2num(4, data[16:20])
            
            length = min(length, SEND_SIZE)
            
            #print "Data request", hex(handle), pos, length
            
            try:
            
                # Match the handle to the file to use.
                fh = self.file_handler[handle]
                
                file_length = fh.length()
                
                fh.seek(pos, 0)
                
                file_data = fh.read(length)
                
                # Calculate the new offset into the file.
                new_pos = pos + len(file_data)
                
                # Write the message header.
                header = ["S"+reply_id, len(file_data), 0xc]
                
                self.log("sent", header, address)
                
                # Encode the header, adding padding if necessary.
                header = self._encode(header)
                
                # Add a 12 byte trailer onto the end of the data
                # containing the amount of data sent and the new
                # offset into the file being read.
                trailer = ["B"+reply_id, len(file_data), new_pos]
                
                self.log("sent", trailer, address)
                
                # Encode the trailer, adding padding if necessary.
                trailer = self._encode(trailer)
                
                # Construct the message string.
                msg = header + file_data + trailer
            
            except (KeyError, IOError):
            
                # Reply with an error message.
                msg = self._encode(["E"+reply_id, 0x100d6, "Not found"])
            
            # Send the message.
            _socket.sendto(msg, address)
        
        elif (command == "A" or command == "B") and code == 0xd:
        
            # Rebroadcasted request for information.
            
            # Reply with an error message.
            msg = ["E"+reply_id, 0x163ac, "Shared disc not available."]
            
            self._send_list(msg, _socket, address)
        
        elif command == "D":
        
            # Request for data to be sent.
            self.share_messages.append(data)
        
        elif command == "R":
        
            # Reply from a successful open request.
            self.share_messages.append(data)
        
        elif command == "S":
        
            # Successful request for a catalogue.
            self.share_messages.append(data)
        
        elif command == "E":
        
            # Error response to a request.
            self.share_messages.append(data)
            
            print "%s (%i)" % (
                self.read_string(data[8:], ending = "\000", include = 0),
                self.str2num(4, data[4:8])
                )
        
        elif command == "F":
        
            # Resource updated
            pass
        
        elif command == "d":
        
            # Data sent to this client for uploading.
            self.share_messages.append(data)
        
        elif command == "r":
        
            # Data sent to this client for uploading.
            self.share_messages.append(data)
        
        elif command == "w":
        
            # Request for data to be sent to a remote client for uploading.
            self.share_messages.append(data)
        
        else:
        
            #self.log("received", data, address)
            pass
    
    
    # Method used in listening thread
    
    def listen(self, event):
    
        t0 = time.time()
        
        while 1:
        
            # Read any response.
            self.read_poll_socket()
            self.read_listener_socket()
            self.read_share_socket()
            
            if (time.time() - t0) > TIDY_DELAY:
            
                # Reset the timer and prune the list of transfers.
                t0 = time.time()
                
                items = self.transfers.items()
                
                for path, (thread, host) in items:
                
                    if not thread.isAlive():
                    
                        del self.transfers[path]
                        del self.transfer_events[path]
            
            if event.isSet(): return
    
    def serve(self):
    
        """serve(self)
        
        Make the server available and start serving.
        """
        
        # Make the server available.
        self.broadcast_startup()
        
        # Start the polling thread.
        self.poll_thread.start()
        
        # Start the listening thread.
        self.listen_thread.start()
        
        return
    
    def stop(self):
    
        print "Terminating the listening thread"
        # Terminate the listening thread.
        self.listen_event.set()
        
        # Wait until the thread terminates.
        while self.listen_thread.isAlive():
        
            pass
        
        # Terminate all threads.
        
        # Threads for file transfers to this host
        
        for path, (thread, host) in self.transfers.items():
        
            # Only terminate threads for shares on this host.
            print "Terminating thread for transfer from %s to %s" % \
                (host, path)
            
            # We may wish to avoid doing this to prevent incomplete
            # transfers; we could wait until they have all finished.
            self.transfer_events[path].set()
            
            # Wait until the thread terminates.
            while thread.isAlive():
            
                pass
        
        # Threads for share broadcasts
        
        for (name, host), share in self.shares.items():
        
            # Only terminate threads for shares on this host.
            if host == Hostaddr:
            
                print "Terminating thread for share: %s" % name
                self.shares[(name, host)].event.set()
                
                thread = self.shares[(name, host)].thread
                
                # Wait until the thread terminates.
                while thread.isAlive():
                
                    pass
        
        print "Terminating the polling thread"
        # Terminate the polling thread.
        self.poll_event.set()
        
        # Wait until the thread terminates.
        while self.poll_thread.isAlive():
        
            pass
    
    def fwshow(self):
    
        """fwshow(self)
        
        Show a list of known clients and their shared resources.
        """
        
        if self.clients != {}:
        
            print "Type 5 (Hosts)"
            
            for (name, host), info in self.clients.items():
            
                marker = [" ", "*"][host == Hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
        
        if self.shares != {}:
        
            print "Type 1 (Discs)"
            
            for (name, host) in self.shares.keys():
            
                marker = [" ", "*"][host == Hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
        
        if self.printers != {}:
        
            print "Type 2 (Printers)"
            
            for (name, host) in self.printers.keys():
            
                marker = [" ", "*"][host == Hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
    
    def add_share(self, name, directory, mode = 0644, delay = 30,
                  present = "truncate", filetype = DEFAULT_FILETYPE):
    
        """add_share(self, name, directory, mode = 0644, delay = 30,
                     present = "truncate", filetype = DEFAULT_FILETYPE)
        
        Create a Share object and it to the dictionary of shares available
        to other hosts.
        """
        
        if self.shares.has_key((name, Hostaddr)):
        
            print "Share is already available: %s" % name
            return
        
        # Ensure that the values passed are reasonable and that the
        # directory exists.
        try:
        
            if not os.path.isdir(directory):
            
                raise ShareError, "Share directory is invalid: %s" % directory
        
        except OSError:
        
            raise ShareError, "Share directory is invalid: %s" % directory
        
        try:
        
            # Mode value must be valid octal.
            mode = self.coerce(
                string.atoi, (mode, 8), (ValueError,), ShareError,
                "Invalid octal value for mode mask: %s" % mode
                )
            
            # Delay value must be decimal, "off" or "default".
            if delay == "default":
            
                delay = DEFAULT_SHARE_DELAY
            
            elif delay == "off":
            
                pass
            
            else:
            
                delay = self.coerce(
                    float, (delay,), (ValueError,), ShareError,
                    "Invalid delay value: %s" % delay
                    )
            
            # Filetype value must be valid hexadecimal.
            filetype = self.coerce(
                string.atoi, (filetype, 16), (ValueError,), ShareError,
                "Invalid hexadecimal value for filetype: %s" % filetype
                )
            
            share = Share(
                name, directory, mode, delay, present, filetype,
                self.file_handler
                )
            
            self.shares[(name, Hostaddr)] = share
        
        except ShareError:
        
            sys.stderr.write("Share could not be created: %s\n" % name)
    
    def remove_share(self, name):
    
        """remove_share(self, name)
        
        Remove the named share from the shares available to other hosts.
        """
        
        if not self.shares.has_key((name, Hostaddr)):
        
            print "Share is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        event = self.shares[(name, Hostaddr)].event
        
        event.set()
        
        thread = self.shares[(name, Hostaddr)].thread
        
        # Wait until the thread terminates.
        while thread.isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.shares[(name, Hostaddr)]
    
    def add_printer(self, name):
    
        """add_printer(self, name)
        
        Make the named printer available to other hosts.
        """
        
        if self.printers.has_key((name, Hostaddr)):
        
            print "Printer is already available: %s" % name
            return
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.printer_events[name] = event
        
        # Create a thread to run the share broadcast loop.
        thread = threading.Thread(
            group = None, target = self.broadcast_printer,
            name = 'Printer "%s"' % name, args = (name, event),
            kwargs = {"protected": protected, "delay": delay}
            )
        
        self.printers[(name, Hostaddr)] = thread
        
        # Start the thread.
        thread.start()
    
    def remove_printer(self, name):
    
        """remove_printer(self, name)
        
        Withdraw the named printer from service.
        """
        
        if not self.printers.has_key((name, Hostaddr)):
        
            print "Printer is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.printer_events[name].set()
        
        # Wait until the thread terminates.
        while self.printers[(name, Hostaddr)].isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.printers[(name, Hostaddr)]
        del self.printer_events[name]
    
    def open_share(self, name, host):
    
        try:
        
            return self.open_shares[(name, host)]
        
        except KeyError:
        
            pass
        
        share = RemoteShare(name, host, self.share_messages)
        
        info = share.open("")
        
        if info is not None:
        
            self.open_shares[(name, host)] = share
            return share
        
        else:
        
            return None
