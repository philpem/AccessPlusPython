"""
    tools.py
    
    Tools for examining data send via UDP from an Access+ station.
"""

import os, string, socket, sys, time, threading, types


default_filetype = 0xffd


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
    
    def new_id(self):
    
        if not hasattr(self, "_id"):
        
            self._id = 1
        
        else:
        
            self._id = self._id + 0x1001
            if self._id > 0xffffff:
                self._id = 1
        
        return "%s" % self.number(3, self._id)
    
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
            
            lines.append("%s : %s\n" % (words, s))
            
            i = i + 16
        
        return lines
    
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
    
    to_riscos = {".": "/", " ": "\xa0"}
    
    def riscos_filename(self, name):
    
        new = []
        
        for c in name:
        
            if self.to_riscos.has_key(c):
            
                new.append(self.to_riscos[c])
            
            else:
            
                new.append(c)
        
        return string.join(new, "")
    
    def read_mimemap(self):
    
        # Compile a list of paths to check for the MimeMap file.
        paths = [""]
        
        # Look for a MimeMap file in the path used to invoke this program.
        path, file = os.path.split(sys.argv[0])
        paths.append(path)
        
        f = None
        
        for path in paths:
        
            try:
            
                f = open(os.path.join(path, "MimeMap"), "r")
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
        
            # Strip trailing whitespace and split the string.
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
        
        # Return the mappings.
        return mappings
    
    def suffix_to_filetype(self, filename):
    
        # Find the appropriate filetype to use for the filename given.
        at = string.rfind(filename, os.extsep)
        
        if at == -1:
        
            # No suffix: return the default filetype.
            return default_filetype
        
        # The suffix includes the "." character. Remove this platform's
        # separator and replace it with a ".".
        suffix = "." + filename[at+len(os.extsep):]
        
        # Find the suffix in the list of mappings.
        for mapping in self.mimemap:
        
            if suffix in mapping["Extensions"]:
            
                # Return the corresponding filetype for this suffix.
                try:
                
                    return string.atoi(mapping["Hex"], 16)
                   
                except ValueError:
                
                    # The value found was not in a valid hexadecimal
                    # representation. Return the default filetype.
                    return default_filetype
        
        # No mappings declared the suffix used.
        return default_filetype



class Unused(Common):

    def _read_port(self, port):
    
        if not self.ports.has_key(port):
        
            print "No socket to use for port %i" % port
            return []
        
        s = self.ports[port]
        
        try:
        
            data, address = s.recvfrom(1024)
            
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



class Peer(Common):

    def __init__(self):
    
        # ---------------------------------------------------------------------
        # Read configuration files
        
        # Read the MimeMap file. This method is defined in the Common class
        # definition.
        self.mimemap = self.read_mimemap()
        
        # ---------------------------------------------------------------------
        # Socket configuration
        
        # Define a global hostname variable to represent this machine on the local
        # subnet.
        
        self.hostname = socket.gethostname()
        
        self.hostaddr = socket.gethostbyname(self.hostname)
        
        at = string.rfind(self.hostaddr, ".")
        
        self.broadcast = self.hostaddr[:at] + ".255"
        
        self.identity = "1234"
        
        # Use just the hostname from the full hostname retrieved.
        
        at = string.find(self.hostname, ".")
        
        if at != -1:
        
            self.hostname = self.hostname[:at]
        
        # Define a dictionary to relate port numbers to the sockets
        # to use.
        self.broadcasters = {}
        self.ports = {}
        
        # Create sockets to use for polling.
        self._create_poll_sockets()
        
        # Create sockets to use for listening.
        self._create_listener_sockets()
        
        # Create sockets to use for share details.
        self._create_share_sockets()
        
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
        
        # Maintain a dictionary of known clients, shares and printers.
        # Each of these will use a separate thread.
        self.clients = {}
        self.shares = {}
        self.printers = {}
        
        # Keep a dictionary of events to use to communicate with threads.
        self.share_events = {}
        self.printer_events = {}
        
        # Create lists of messages sent to each listening socket.
        self.share_messages = []
        
        # Maintain a dictionary of open shares, on the local host or
        # on other hosts.
        # Each entry in this dictionary is referenced by a tuple containing
        # the name of the share and the host it resides on and contains the
        # ID value used to open it.
        self.open_shares = {}
    
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
    
    def _create_poll_sockets(self):
    
        self._poll_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._poll_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._poll_s.setblocking(0)
        
        self._poll_s.bind((self.broadcast, 32770))
        
        self.broadcasters[32770] = self._poll_s
        
        # Create a socket for listening.
        self._poll_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the socket to be non-blocking.
        self._poll_l.setblocking(0)
        
        self._poll_l.bind((self.hostaddr, 32770))
        
        self.ports[32770] = self._poll_l
    
    def _create_listener_sockets(self):
    
        self._listen_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._listen_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._listen_s.setblocking(0)
        
        self._listen_s.bind((self.broadcast, 32771))
        
        self.broadcasters[32771] = self._listen_s
        
        # Create a socket for listening.
        self._listen_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the socket to be non-blocking.
        self._listen_l.setblocking(0)
        
        self._listen_l.bind((self.hostaddr, 32771))
        
        self.ports[32771] = self._listen_l
    
    def _create_share_sockets(self):
    
        self._share_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._share_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._share_s.setblocking(0)
        
        self._share_s.bind((self.broadcast, 49171))
        
        self.broadcasters[49171] = self._share_s
        
        # Create a socket for listening.
        self._share_l = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the socket to be non-blocking.
        self._share_l.setblocking(0)
        
        self._share_l.bind((self.hostaddr, 49171))
        
        self.ports[49171] = self._share_l
    
    def _send_list(self, l, s, to_addr):
    
        """send_list(self, list, socket, to_addr)
        
        Encode the list as a string suitable for other Access+ clients
        using the _encode method then send it on the socket provided.
        """
        
        s.sendto(self._encode(l), to_addr)
    
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
        
        self._send_list(data, s, (self.broadcast, 32770))
        
        # Create the second message to send.
        data = [0x00050001, 0x00000000]
        
        self._send_list(data, s, (self.broadcast, 32770))
        
        # Create the host broadcast string.
        data = \
        [
            0x00050002, 0x00010000,
            (len(self.identity) << 16) | len(self.hostname),
            self.hostname + self.identity
        ]
        
        self._send_list(data, s, (self.broadcast, 32770))
    
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
            (len(self.identity) << 16) | len(self.hostname),
            self.hostname + self.identity
        ]
        
        while 1:
        
            self._send_list(data, s, (self.broadcast, 32770))
            
            t0 = time.time()
            
            while (time.time() - t0) < delay:
            
                if event.isSet(): return
    
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
        
        self._send_list(data, s, (self.broadcast, 32770))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        # Broadcast a notification to other clients.
        
        for i in range(0, 5):
        
            self._send_list(data, s, (self.broadcast, 49171))
            
            time.sleep(1)
        
        # Remind other clients of the availability of this share.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010004, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
        
        while 1:
        
            self._send_list(data, s, (self.broadcast, 32770))
            
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
        
        self._send_list(data, s, (self.broadcast, 32770))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        while 1:
        
            self._send_list(data, s, (self.broadcast, 49171))
            
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
        
        self._send_list(data, s, (self.broadcast, 32771))
        
        # Advertise the share on the share socket.
        
        if not self.broadcasters.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.broadcasters[49171]
        
        # Create a string to send.
        data = [0x00000046, 0x00000013, 0x00000000]
        
        # Broadcast a notification to other clients.
        
        for i in range(0, 5):
        
            self._send_list(data, s, (self.broadcast, 49171))
            
            time.sleep(1)
        
        while 1:
        
            self._send_list(data, s, (self.broadcast, 32770))
            
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
            (len(self.identity) << 16) | len(self.hostname),
            self.hostname + self.identity
        ]
        
        self._send_list(data, s, (host, 32770))
        
        self.read_port([32770, 32771, 49171])
    
    def read_poll_socket(self):
    
        # Read the listening socket first.
        try:
        
            s = self.ports[32770]
            data, address = s.recvfrom(1024)
            
            self._read_poll_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[32770]
            data, address = s.recvfrom(1024)
            
            self._read_poll_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
    
    def _read_poll_socket(self, data, address):
    
        print "From: %s:%i" % address
        
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
                print "Starting up shares"
            
            elif minor == 0x0002:
            
                # Share made available
                
                if share_type == 0x00010000:
                
                    # A string follows the leading three words.
                    share_name = data[12:12+length1]
                    
                    c = 12 + length1
                    
                    # The protected flag follows the last byte in the string.
                    protected = self.str2num(length2, data[c:c+length2])
                    
                    if protected not in [0, 1]: protected = 0
                    
                    print 'Share "%s" (%s) available' % \
                        (share_name, ["unprotected", "protected"][protected])
                    
                    # Compare the share with those recorded.
                    
                    if not self.shares.has_key((share_name, host)):
                    
                        # Add the share share_name and host to the shares dictionary.
                        self.shares[(share_name, host)] = (None, None)
                
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
                
                print 'Share "%s" (%s) withdrawn' % \
                    (share_name, ["unprotected", "protected"][protected])
                
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
                
                print 'Share "%s" (%s)' % \
                    (share_name, ["unprotected", "protected"][protected])
                
                # Compare the share with those recorded.
                
                if not self.shares.has_key((share_name, host)):
                
                    # Add the share name and host to the shares dictionary.
                    self.shares[(share_name, host)] = (None, None)
            
            else:
            
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
            
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        
        # Type 5 (Hosts)
        
        elif major == 0x0005:
        
            # A client
            
            if minor == 0x0001:
            
                # Startup
                print "Starting up client"
            
            elif minor == 0x0002:
            
                # Startup broadcast
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                print "Startup client: %s %s" % (client_name, info)
            
            elif minor == 0x0003:
            
                # Query message (direct)
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                print "Query: %s %s" % (client_name, info)
            
            elif minor == 0x0004:
            
                # Availability broadcast
                
                # A string follows the leading three words.
                client_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The string following the client name contains some
                # information about the client.
                info = data[c:c+length2]
                
                print "Client available: %s %s" % (client_name, info)
                
                # Compare the client with those in the clients dictionary.
                
                if not self.clients.has_key((client_name, host)):
                
                    # Add an entry for the client to the dictionary.
                    self.clients[(client_name, host)] = info
            
            else:
            
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        else:
        
            lines = self.interpret(data)
            
            for line in lines:
            
                print line
    
    def read_listener_socket(self):
    
        # Read the listening socket first.
        try:
        
            s = self.ports[32771]
            data, address = s.recvfrom(1024)
            
            self._read_listener_socket(data, address)
        
        except (KeyError, socket.error):
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[32771]
            data, address = s.recvfrom(1024)
            
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
            data, address = s.recvfrom(1024)
            
            self._read_share_socket(s, data, address)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
        
        try:
        
            s = self.broadcasters[49171]
            data, address = s.recvfrom(1024)
            
            self._read_share_socket(s, data, address)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
    
    def _read_share_socket(self, _socket, data, address):
    
        print "From: %s:%i" % address
        
        lines = self.interpret(data)
        
        for line in lines:
        
            print line
        
        print
        
        host = address[0]
        
        if data[0] == "A":
        
            # Attempt to open the directory.
            share_name = self.read_string(
                data[12:], ending = "\000", include = 0
                )
            
            print 'Request to open "%s"' % share_name
            
            if self.shares.has_key((share_name, self.hostaddr)):
            
                # For unprotected shares, reply with details of the share.
                
                # Use the first word given but substitute "R" for "A".
                msg = ["R"+data[1:4], 0xffffcd00, 0, 0x800, 0x13, 0x102, 0]
                
                print "Sent:"
                for line in self.interpret(self._encode(msg)):
                
                    print line
                print
                
                #msg = "R"+data[1:4] + '\x00\xcd\xff\xff\x00\x00\x00\x00\x00\x08\x00\x00\x13\x00\x00\x00\x02\x01\x00\x00\x01:\xa6\x04'
                
                self._send_list(msg, _socket, address)
                #_socket.sendto(msg, address)
            
            else:
            
                # Reply with an error message.
                self._send_list(
                    ["E"+data[1:4], 0x163ac, "Shared disc not available."],
                    _socket, address
                    )
        
        elif data[0] == "B" and self.str2num(4, data[4:8]) == 0x3:
        
            # Request for information.
            
            share_name = self.read_string(
                data[16:], ending = "\000", include = 0
                )
            
            print 'Request to catalogue "%s"' % share_name
            
            try:
            
                # For unprotected shares, return a catalogue to the client.
                
                thread, direct = self.shares[(share_name, self.hostaddr)]
                
                files = os.listdir(direct)
                
                # Write the message, starting with the code and ID word.
                msg = ["S"+data[1:4]]
                
                # Write the catalogue information.
                
                # The first word is the length of the directory structure
                # information.
                # Calculate this later.
                msg.append(0)
                
                # The next word is the length of the following share
                # information.
                msg.append(0x24)

                dir_length = 0
                
                # Count the number of files to be sent. More than 77 files
                # may cause problems. We will use os.stat to check for
                # objects which are not files or directories.
                
                n_files = 0
                
                new_files = []
                
                for file in files:
                
                    if string.find(file, os.extsep) == 0:
                    
                        continue
                    
                    try:
                    
                        os.stat(os.path.join(direct, file))
                        n_files = n_files + 1
                        new_files.append(file)
                    
                    except OSError:
                    
                        pass
                    
                    # If 77 files have been listed then list no more.
                    if n_files == 77: break
                
                print "%i files found."
                
                n_files = 0
                
                for file in new_files:
                
                    file_msg = []
                    length = 0
                    
                    path = os.path.join(direct, file)
                    
                    try:
                    
                        # Filetype word
                        if os.path.isdir(path):
                        
                            file_msg.append(0xfffffd49)
                        
                        else:
                        
                            # Use the suffix of the file to generate a
                            # filetype.
                            filetype = self.suffix_to_filetype(file)
                            file_msg.append(0xfff0004b | (filetype << 8))
                        
                        length = length + 4
                        
                        # Unknown word
                        file_msg.append(0)
                        length = length + 4
                        
                        # Length word (0x800 for directory)
                        if os.path.isdir(path):
                        
                            file_msg.append(0x800)
                        
                        else:
                        
                            file_msg.append(os.path.getsize(path))
                        
                        length = length + 4
                        
                        # Flags word (0x10 for directory)
                        if os.path.isdir(path):
                        
                            file_msg.append(0x10)
                        
                        else:
                        
                            file_msg.append(0x03)
                        
                        length = length + 4
                        
                        # Flags word (0x2 for directory)
                        if os.path.isdir(path):
                        
                            file_msg.append(0x02)
                        
                        else:
                        
                            file_msg.append(0x01)
                        
                        length = length + 4
                        
                        # Convert the name into a form suitable for the
                        # other client.
                        file_name = self.riscos_filename(file)
                        
                        # Zero terminated name string
                        name_string = self._encode([file_name + "\000"])
                        
                        file_msg.append(name_string)
                        
                        length = length + len(name_string)
                        
                        n_files = n_files + 1
                    
                    except OSError:
                    
                        file_msg = []
                        length = 0
                    
                    msg = msg + file_msg
                    dir_length = dir_length + length
                
                # The data following the directory structure is concerned
                # with the share and is like a return value from a share
                # open request but with a "B" command word like a
                # catalogue request.
                msg = msg + \
                [
                    "B"+data[1:4], 0xffffcd00, 0x00000000, 0x00000800,
                       0x00000013, 0x00000002, 0x00000000, dir_length,
                       0xffffffff
                ]
                
                # Fill in the directory length.
                msg[1] = dir_length
                
                # Send the reply.
                self._send_list(msg, _socket, address)
                
                print
                print "Sent:"
                for line in self.interpret(self._encode(msg)):
                
                    print line
                print
            
            except (KeyError, OSError):
            
                # Reply with an error message.
                self._send_list(
                    ["E"+data[1:4], 0x163ac, "Shared disc not available."],
                    _socket, address
                    )
        
        elif data[0] == "B" and self.str2num(4, data[4:8]) == 0xd:
        
            # Rebroadcasted request for information.
            
            # Reply with an error message.
            self._send_list(
                ["E"+data[1:4], 0x163ac, "Shared disc not available."],
                _socket, address
                )
        
        elif data[0] == "R":
        
            # Reply from a successful open request.
            self.share_messages.append(data)
        
        elif data[0] == "S":
        
            # Successful request for a catalogue.
            self.share_messages.append(data)
        
        elif data[0] == "E":
        
            # Error response to a request.
            self.share_messages.append(data)
            
            print "%s (%i)" % (
                self.read_string(data[8:], ending = "\000", include = 0),
                self.str2num(4, data[4:8])
                )
    
    def listen(self, event):
    
        while 1:
        
            # Read any response.
            response = self.read_poll_socket()
            respones = self.read_listener_socket()
            response = self.read_share_socket()
            
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
        
        # Serve in a loop which can be terminated by a keyboard interrupt
        # (CTRL-C).
        try:
        
            while 1:
            
                self._serve()
        
        except KeyboardInterrupt:
        
            pass
    
    def _serve(self):
    
        pass
    
    def stop(self):
    
        print "Terminating the listening thread"
        # Terminate the listening thread.
        self.listen_event.set()
        
        # Wait until the thread terminates.
        while self.listen_thread.isAlive():
        
            pass
        
        # Terminate all threads.
        for (name, host), (thread, directory) in self.shares.items():
        
            # Only terminate threads for shares on this host.
            if host == self.hostaddr:
            
                print "Terminating thread for share: %s" % name
                self.share_events[name].set()
                
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
            
                marker = [" ", "*"][host == self.hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
        
        if self.shares != {}:
        
            print "Type 1 (Discs)"
            
            for (name, host) in self.shares.keys():
            
                marker = [" ", "*"][host == self.hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
        
        if self.printers != {}:
        
            print "Type 2 (Printers)"
            
            for (name, host) in self.printers.keys():
            
                marker = [" ", "*"][host == self.hostaddr]
                
                print string.expandtabs(
                    "   %sName=%s\tHolder=%s" % (marker, name, host), 12
                    )
            
            print
    
    def add_share(self, name, directory, protected = 0, delay = 30):
    
        """add_share(self, name, directory, protected = 0, delay = 30)
        
        Add the named share to the shares available to other hosts.
        """
        
        if self.shares.has_key((name, self.hostaddr)):
        
            print "Share is already available: %s" % name
            return
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.share_events[name] = event
        
        # Create a thread to run the share broadcast loop.
        thread = threading.Thread(
            group = None, target = self.broadcast_share,
            name = 'Share "%s"' % name, args = (name, event),
            kwargs = {"protected": protected, "delay": delay}
            )
        
        self.shares[(name, self.hostaddr)] = (thread, directory)
        
        # Start the thread.
        thread.start()
    
    def remove_share(self, name):
    
        """remove_share(self, name)
        
        Remove the named share from the shares available to other hosts.
        """
        
        if not self.shares.has_key((name, self.hostaddr)):
        
            print "Share is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.share_events[name].set()
        
        thread, directory = self.shares[(name, self.hostaddr)]
        
        # Wait until the thread terminates.
        while thread.isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.shares[(name, self.hostaddr)]
        del self.share_events[name]
    
    def add_printer(self, name):
    
        """add_printer(self, name)
        
        Make the named printer available to other hosts.
        """
        
        if self.printers.has_key((name, self.hostaddr)):
        
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
        
        self.printers[(name, self.hostaddr)] = thread
        
        # Start the thread.
        thread.start()
    
    def remove_printer(self, name):
    
        """remove_printer(self, name)
        
        Withdraw the named printer from service.
        """
        
        if not self.printers.has_key((name, self.hostaddr)):
        
            print "Printer is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.printer_events[name].set()
        
        # Wait until the thread terminates.
        while self.printers[(name, self.hostaddr)].isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.printers[(name, self.hostaddr)]
        del self.printer_events[name]
    
    def open_share(self, name, host):
    
        """open_share(self, name, host)
        
        Open a share of a given name on the host specified.
        """
        
        # Use the non-broadcast socket.
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.ports[49171]
        
        # Create a string to send. The three bytes following the "A"
        # character are used to identify the response from the other
        # client (it passes them back).
        new_id = self.new_id()
        
        data = ["A"+new_id, 1, 0, name]
        
        # Send the request.
        self._send_list(data, s, (host, 49171))
        
        replied = 0
        tries = 5
        
        # Keep a record of the time of the previous request.
        t0 = time.time()
        
        while replied == 0 and tries > 0:
        
            # See if the response has arrived.
            for data in self.share_messages:
            
                if data[:4] == "R"+new_id:
                
                    print 'Successfully opened "%s"' % name
                    self.share_messages.remove(data)
                    
                    replied = 1
                    
                    break
                
                elif data[:4] == "E"+new_id:
                
                    print 'Error: "%s"' % data[8:]
                    self.share_messages.remove(data)
                    
                    return
            
            t1 = time.time()
            
            if replied == 0 and (t1 - t0) > 1.0:
            
                # Send the request again.
                self._send_list(data, s, (host, 49171))
                
                t0 = t1
                tries = tries - 1
        
        if replied == 0:
        
            print "The machine containing the shared disc does not respond"
            return
        
        # Set the open share details.
        self.open_shares[(name, host)] = None
    
    def catalogue(self, name, host):
    
        """lines = catalogue(self, name, host)
        
        Return a catalogue of the files on the named share on the host
        given.
        """
        
        if not self.open_shares.has_key((name, host)):
        
            # This may be required for mounting purposes.
            pass
        
        
        # Use the non-broadcast socket.
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.ports[49171]
        
        # Create a string to send. The three bytes following the "B"
        # character are used to identify the response from the other
        # client (it passes them back). We retrieve them from a
        # dictionary.
        new_id = self.new_id()
        
        data = ["B"+new_id, 3, 0xffffffff, 0, name]
        
        # Send the request.
        self._send_list(data, s, (host, 49171))
        
        replied = 0
        tries = 5

        # Keep a record of the time of the previous request.
        t0 = time.time()
        
        while replied == 0 and tries > 0:
        
            # See if the response has arrived.
            for data in self.share_messages:
            
                if data[:4] == "S"+new_id:
                
                    self.share_messages.remove(data)
                    
                    self.data = data
                    
                    # Catalogue information was returned.
                    self.open_shares[(name, host)] = new_id
                    replied = 1
                    
                    break
                
                elif data[:4] == "E"+new_id:
                
                    self.share_messages.remove(data)
                    
                    return []
            
            t1 = time.time()
            
            if replied == 0 and (t1 - t0) > 1.0:
            
                # Send the request again.
                self._send_list(data, s, (host, 49171))
                
                t0 = t1
                tries = tries - 1
        
        if replied == 0:
        
            print "The machine containing the shared disc does not respond"
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
            unknown = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Length word (0x800 for directory)
            length = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Flags word (0x10 for directory)
            flags1 = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Flags word (0x2 for directory)
            flags2 = self.str2num(4, data[c:c+4])
            c = c + 4
            
            # Zero terminated name string
            name = self.read_string(
                data, offset = c, ending = "\000", include = 0
                )
            
            c = c + len(name) + 1
            
            if c % 4 != 0:
            
                c = c + 4 - (c % 4)
            
            files.append( (filetype_word, unknown, length, flags1, flags2, name) )
            lines.append(
                "%s: %03x (%i bytes) %i %i" % (
                    name, filetype, length, flags1, flags2
                    )
                )
        
        # The data following the directory structure is concerned
        # with the share and is like a return value from a share
        # open request but with a "B" command word like a
        # catalogue request.
        
        # The second to last word is the root entry.
        self.open_shares[(name, host)] = self.str2num(4, data[-8:-4])
