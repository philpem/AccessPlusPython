"""
    tools.py
    
    Tools for examining data send via UDP from an Access+ station.
"""

import string, socket, sys, time, threading, types


# Define dummy values to use for constants with the _decode methd.
# We could use enumerate but this is just as easy as the values will be
# ignored; their types are the important pieces of information.


class Access:

    def __init__(self):
    
        # Define a global hostname variable to represent this machine on the local
        # subnet.
        
        self.hostname = socket.gethostname()
        
        self.hostaddr = socket.gethostbyaddr(self.hostname)[2][0]
        
        at = string.rfind(self.hostaddr, ".")
        
        self.broadcast = self.hostaddr[:at] + ".255"
        
        # Use just the hostname from the full hostname retrieved.
        
        at = string.find(self.hostname, ".")
        
        if at != -1:
        
            self.hostname = self.hostname[:at]
        
        padding = 4 - (len(self.hostname) % 4)
        if padding == 4: padding = 0
        
        self.pad_hostname = self.hostname + (padding * "\000")
        
        # Define a dictionary to relate port numbers to the sockets
        # to use.
        self.ports = {}
        
        # Create a socket to use for polling.
        self._create_poll_socket()
        
        # Create a socket to use for listening.
        self._create_listener_socket()
        
        # Create a socket to use for share details.
        self._create_share_socket()
    
    def __del__(self):
    
        # Close all sockets.
        for port, _socket in self.ports.items():
        
            print "Closing socket for port %i" % port
            _socket.close()
    
    def _create_poll_socket(self):
    
        self._poll_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._poll_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._poll_s.setblocking(0)
        
        self._poll_s.bind((self.broadcast, 32770))
        
        self.ports[32770] = self._poll_s
    
    def _create_listener_socket(self):
    
        self._listen_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._listen_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._listen_s.setblocking(0)
        
        self._listen_s.bind((self.broadcast, 32771))
        
        self.ports[32771] = self._listen_s
    
    def _create_share_socket(self):
    
        self._share_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow the socket to broadcast packets.
        self._share_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set the socket to be non-blocking.
        self._share_s.setblocking(0)
        
        self._share_s.bind((self.broadcast, 49171))
        
        self.ports[49171] = self._share_s
    
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
            
            else:
            
                # Pad the string to fit an integer number of words.
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
    
    def interpret(self, data):
    
        lines = []
        
        i = 0
        
        while i < len(data):
        
            # Print the data in big-endian word form.
            words = []
            j = i
            
            while j < len(data) and j < i + 16:
            
                word = self.str2num(4, data[j:j+4])
                
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
    
    def _read_port(self, port):
    
        if not self.ports.has_key(port):
        
            print "No socket to use for port %i" % port
            return []
        
        s = self.ports[port]
        
        try:
        
            data = s.recv(1024)
            
            lines = self.interpret(data)
        
        except socket.error:
        
            lines = []
        
        return lines
    
    def read_port(self, ports):
    
        t0 = time.time()
        
        try:
        
            while 1:
            
                t = int(time.time() - t0)
                
                for port in ports:
                
                    lines = self._read_port(port)
                    
                    if lines != []:
                    
                        print "Port %i:" % port
                        
                        for line in lines:
                        
                            print line
                        
                        print
        
        except KeyboardInterrupt:
        
            pass
    
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
        
        if not self.ports.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.ports[32770]
        
        # Create the first string to send.
        data = \
            self.number(4, 0x00010001) + \
            self.number(4, 0x00000000)
        
        s.sendto(data, (self.broadcast, 32770))
        
        # Create the second string to send.
        data = \
            self.number(4, 0x00050001) + \
            self.number(4, 0x00000000)
        
        s.sendto(data, (self.broadcast, 32770))
        
        # Create the host broadcast string.
        data = \
            self.number(4, 0x00050002) + \
            self.number(4, 0x00010000) + \
            self.number(4, 0x00040000 | len(self.hostname)) + \
            self.pad_hostname + \
            self.number(4, 0x00003eb9)
        
        s.sendto(data, (self.broadcast, 32770))
    
    def broadcast_poll(self, event, delay = 20):
    
        """broadcast_poll(self)
        
        Broadcast a poll on port 32770 every few seconds. Never exits.
        """
        
        if not self.ports.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.ports[32770]
        
        # Create a string to send.
        data = \
            self.number(4, 0x00050004) + \
            self.number(4, 0x00010000) + \
            self.number(4, 0x00040000 | len(self.hostname)) + \
            self.pad_hostname + \
            self.number(4, 0x00003eb9)
        
        while 1:
        
            t0 = time.time()
            
            s.sendto(data, (self.broadcast, 32770))
            
            while int(time.time() - t0) < delay:
            
                # Read any response.
                response = self.read_poll_socket(s)
                
                if event.isSet(): return
            
    def read_poll_socket(self, s):
    
        try:
        
            data = s.recv(1024)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
        
        # Check the first word of the response to determine what the
        # information is about.
        about = self.str2num(4, data[:4]) 
        
        if about & 0xffff0000 == 0x00010000:
        
            # A share
            
            if about & 0xffff == 0x0000:
            
                # Startup
                print "Starting up shares"
            
            elif about & 0xffff == 0x0002:
            
                # Share made available
                
                # Ignore the second word
                
                # The first byte of the third word contains the length of
                # the share name string.
                
                length = self.str2num(1, data[8])
                
                # The string follows in the next word.
                share_name = data[12:12+length]
                
                # The protected flag follows the last byte in the string.
                protected = data[12+length]
                
                print 'Share "%s" (%s) available' % \
                    (share_name, ["unprotected", "protected"][protected])
            
            elif about & 0xffff == 0x0003:
            
                # Share withdrawn
                
                # Ignore the second word
                
                # The first byte of the third word contains the length of
                # the share name string.
                
                length = self.str2num(1, data[8])
                
                # The string follows in the next word.
                share_name = data[12:12+length]
                
                # The protected flag follows the last byte in the string.
                protected = data[12+length]
                
                print 'Share "%s" (%s) withdrawn' % \
                    (share_name, ["unprotected", "protected"][protected])
        
        elif about & 0xffff0000 == 0x00050000:
        
            # A client
            
            if about & 0xffff == 0x0001:
            
                # Startup
                print "Starting up client"
            
            elif about & 0xffff == 0x0002:
            
                # Startup broadcast
                
                # Ignore the second word
                
                # The first byte of the third word contains the length of
                # the share name string.
                
                length = self.str2num(1, data[8])
                
                # The string follows in the next word.
                client_name = data[12:12+length]
                
                c = 12 + length
                
                if c % 4 != 0:
                
                    c = c + 4 - (c % 4)
                
                # The word following the client name contains some
                # information about the client.
                info = self.str2num(4, data[c:c+4])
                
                print "Startup client: %s %08x" % (client_name, info)
            
            elif about & 0xffff == 0x0003:
            
                # Query message (direct)
                
                # Ignore the second word
                
                # The first byte of the third word contains the length of
                # the share name string.
                
                length = self.str2num(1, data[8])
                
                # The string follows in the next word.
                client_name = data[12:12+length]
                
                c = 12 + length
                
                if c % 4 != 0:
                
                    c = c + 4 - (c % 4)
                
                # The word following the client name contains some
                # information about the client.
                info = self.str2num(4, data[c:c+4])
                
                print "Query: %s %08x" % (client_name, info)
            
            elif about & 0xffff == 0x0004:
            
                # Availability broadcast
                
                # Ignore the second word
                
                # The first byte of the third word contains the length of
                # the share name string.
                
                length = self.str2num(1, data[8])
                
                # The string follows in the next word.
                client_name = data[12:12+length]
                
                c = 12 + length
                
                if c % 4 != 0:
                
                    c = c + 4 - (c % 4)
                
                # The word following the client name contains some
                # information about the client.
                info = self.str2num(4, data[c:c+4])
                
                print "Client available: %s %08x" % (client_name, info)
    
    
    def broadcast_share(self, name, event, protected = 0, delay = 2):
    
        """broadcast_share(self, name, event, protected = 0, delay = 2)
        
        Broadcast the availability of a share every few seconds.
        """
        
        # Pad the name of the share to fit an integer number of words.
        padding = 4 - (len(name) % 4)
        
        if padding == 4: padding = 0
        
        pad_name = name + (padding * "\000")
        
        # Broadcast the availability of the share on the polling socket.
        
        if not self.ports.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.ports[32770]
        
        data = \
            self.number(4, 0x00010002) + \
            self.number(4, 0x00010000) + \
            self.number(4, 0x00010000 | len(name)) + \
            pad_name + \
            self.number(4, 0x00000034 | ((protected & 1) << 8))
        
        # Advertise the share on the share socket.
        
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.ports[49171]
        
        # Create a string to send.
        data = \
            self.number(4, 0x00000046) + \
            self.number(4, 0x00000013) + \
            self.number(4, 0x00000000)
        
        while 1:
        
            t0 = time.time()
            
            s.sendto(data, (self.broadcast, 49171))
            
            while int(time.time() - t0) < delay:
            
                try:
                
                    data = s.recv(1024)
                    
                    sys.stdout.write("Sharing data:\n")
                    self.interpret(data)
                    sys.stdout.flush()
                
                except socket.error:
                
                    if sys.exc_info()[1].args[0] == 11:
                    
                        pass
                
                if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.ports[32770]
        
        data = \
            self.number(4, 0x00010003) + \
            self.number(4, 0x00010000) + \
            self.number(4, 0x00010000 | len(name)) + \
            pad_name + \
            self.number(4, 0x00000034 | ((protected & 1) << 8))
    
    def send_query(self, host):
    
        if not self.ports.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.ports[32770]
        
        # Create a string to send.
        data = \
            self.number(4, 0x00050003) + \
            self.number(4, 0x00010000) + \
            self.number(4, 0x00040000 | len(self.hostname)) + \
            self.pad_hostname + \
            self.number(4, 0x00003eb9)
        
        s.sendto(data, (host, 32770))
        
        self.read_port([32770, 32771, 49171])



class Server:

    def __init__(self):
    
        # Create an Access instance.
        self.access = Access()
        
        # Create an event to use to terminate the polling thread.
        self.poll_event = threading.Event()
        
        # Create a thread to call the broadcast_poll method of the
        # access object.
        self.poll_thread = threading.Thread(
            group = None, target = self.access.broadcast_poll,
            name = "Poller", args = (self.poll_event,),
            kwargs = {"delay": 10}
            )
        
        # Maintain a dictionary of open shares and a dictionary of events
        # to use to communicate with them.
        self.shares = {}
        self.events = {}
    
    def __del__(self):
    
        self.stop()
    
    def serve(self):
    
        """serve(self)
        
        Make the server available and start serving.
        """
        
        # Make the server available.
        self.access.broadcast_startup()
        
        # Start the polling thread.
        self.poll_thread.start()
        
        # For now, just return control to the user.
        return
        
        # Serve in a loop which can be terminated by a keyboard interrupt
        # (CTRL-C).
        try:
        
            while 1:
            
                self._serve(self)
        
        except KeyboardInterrupt:
        
            pass
    
    def _serve(self):
    
        pass
    
    def stop(self):
    
        # Terminate all threads.
        for name, thread in self.shares.items():
        
            print "Terminating thread for share: %s" % name
            self.events[name].set()
            
            # Wait until the thread terminates.
            while self.shares[name].isAlive():
            
                pass
        
        # Terminate the polling thread.
        self.poll_event.set()
        
        # Wait until the thread terminates.
        while self.poll_thread.isAlive():
        
            pass
    
    def add_share(self, name, protected = 0, delay = 2):
    
        """add_share(self, name)
        
        Add the named share to the shares available to other hosts.
        """
        
        if self.shares.has_key(name):
        
            print "Share is already accessible: %s" % name
            return
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.events[name] = event
        
        # Create a thread to run the share broadcast loop.
        thread = threading.Thread(
            group = None, target = self.access.broadcast_share,
            name = 'Share "%s"' % name, args = (name, event),
            kwargs = {"protected": protected, "delay": delay}
            )
        
        self.shares[name] = thread
        
        # Start the thread.
        thread.start()
    
    def remove_share(self, name):
    
        """remove_share(self, name)
        
        Remove the named share from the shares available to other hosts.
        """
        
        if not self.shares.has_key(name):
        
            print "Share is not currently accessible: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.events[name].set()
        
        # Wait until the thread terminates.
        while self.shares[name].isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.shares[name]
        del self.events[name]
    
    def read_port(self, ports):
    
        self.access.read_port(ports)
