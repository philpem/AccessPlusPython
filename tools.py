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
        self._create_poll_socket()
        
        # Create sockets to use for listening.
        self._create_listener_socket()
        
        # Create sockets to use for share details.
        self._create_share_socket()
        
        # Create lists of messages sent to each listening socket.
        self.share_messages = []
        
        # Create lists of open shares on other hosts.
        
    
    def __del__(self):
    
        # Close all sockets.
        for port, _socket in self.broadcasters.items():
        
            print "Closing socket for port %i" % port
            _socket.close()
    
    def _create_poll_socket(self):
    
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
        
        self._poll_l.bind((self.hostname, 32770))
        
        self.ports[32770] = self._poll_l
    
    def _create_listener_socket(self):
    
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
        
        self._listen_l.bind((self.hostname, 32771))
        
        self.ports[32771] = self._listen_l
    
    def _create_share_socket(self):
    
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
        
        self._share_l.bind((self.hostname, 49171))
        
        self.ports[49171] = self._share_l
    
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
    
    def new_id(self):
    
        if not hasattr(self, "_id"):
        
            self._id = 1
        
        else:
        
            self._id = self._id + 1
            if self._id > 0xffffff:
                self._id = 1
        
        return "%s" % self.number(3, self._id)
    
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
            
            while j <= (len(data) - 4) and j < (i + 16):
            
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
    
    def _send_list(self, l, s, to_addr):
    
        """send_list(self, list, socket, to_addr)
        
        Encode the list as a string suitable for other Access+ clients
        using the _encode method then send it on the socket provided.
        """
        
        s.sendto(self._encode(l), to_addr)
    
    def read_poll_socket(self):
    
        if not self.ports.has_key(32770):
        
            print "No socket to use for port %i" % 32770
            return
        
        s = self.ports[32770]
        
        try:
        
            data, address = s.recvfrom(1024)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
        
        print "From: %s:%i" % address
        
        # Check the first word of the response to determine what the
        # information is about.
        about = self.str2num(4, data[:4]) 
        
        major = (about & 0xffff0000) >> 16
        minor = about & 0xffff
        
        # The second word of the response has an unknown meaning.
        
        if self.str2num(4, data[4:8]) != 0:
        
            # The third word contains two half-word length values.
            length1 = self.str2num(2, data[8:10])
            length2 = self.str2num(2, data[10:12])
        
        if major == 0x0001:
        
            # A share
            
            if minor == 0x0001:
            
                # Startup
                print "Starting up shares"
            
            elif minor == 0x0002:
            
                # Share made available
                
                # A string follows the leading three words.
                share_name = data[12:12+length1]
                
                c = 12 + length1
                
                # The protected flag follows the last byte in the string.
                protected = self.str2num(length2, data[c:c+length2])
                
                if protected not in [0, 1]: protected = 0
                
                print 'Share "%s" (%s) available' % \
                    (share_name, ["unprotected", "protected"][protected])
            
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
            
            else:
            
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        
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
            
            elif minor == 0x0003:
            
                # Printer withdrawn
                
                # A string follows the leading three words.
                printer_name = data[12:12+length1]
                
                c = 12 + length1
                
                printer_desc = data[c:c+length2]
                
                c = c + length2
                
                print 'Printer "%s" (%s) withdrawn' % \
                    (printer_name, printer_desc)
            
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
            
            else:
            
                lines = self.interpret(data)
                
                for line in lines:
                
                    print line
        else:
        
            lines = self.interpret(data)
            
            for line in lines:
            
                print line
    
    def read_share_socket(self):
    
        if not self.ports.has_key(49171):
        
            print "No socket to use for port %i" % 49171
            return
        
        s = self.ports[49171]
        
        try:
        
            data, address = s.recvfrom(1024)
        
        except socket.error:
        
            if sys.exc_info()[1].args[0] == 11:
            
                pass
            
            return None
        
        print "From: %s:%i" % address
        
        if data[0] == "A":
        
            # Attempt to open the directory.
            print 'Request to open "%s"' % data[12:]
        
        elif data[0] == "R":
        
            # Successful reply to an open request.
            self.share_messages.append(data)
        
        elif data[0] == "E":
        
            # Error response to a request.
            self.share_messages.append(data)
        
        else:
        
            print self.interpret(data)
            print
        
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
    
    def broadcast_poll(self, event, delay = 20):
    
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
        
            t0 = time.time()
            
            self._send_list(data, s, (self.broadcast, 32770))
            
            while int(time.time() - t0) < delay:
            
                # Read any response.
                response = self.read_poll_socket()
                response = self.read_share_socket()
                
                if event.isSet(): return
    
    def broadcast_share(self, name, event, protected = 0, delay = 10):
    
        """broadcast_share(self, name, event, protected = 0, delay = 10)
        
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
        
        while 1:
        
            t0 = time.time()
            
            self._send_list(data, s, (self.broadcast, 49171))
            
            while int(time.time() - t0) < delay:
            
                # Read any response.
                #response = self.read_share_socket()
                
                if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010003, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
        ]
    
    def broadcast_printer(self, name, description, event,
                          protected = 0, delay = 2):
    
        """broadcast_share(self, name, description, event,
                           protected = 0, delay = 2)
        
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
        
            t0 = time.time()
            
            self._send_list(data, s, (self.broadcast, 49171))
            
            while int(time.time() - t0) < delay:
            
                # Read any response.
                #response = self.read_share_socket(s)
                
                if event.isSet(): return
        
        # Broadcast that the share has now been removed.
        
        s = self.broadcasters[32770]
        
        data = \
        [
            0x00010003, 0x00010000, 0x00010000 | len(name),
            name + chr(protected & 1)
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
    
    def open_share(self, name, host):
    
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
        
        self._send_list(data, s, (host, 49171))
        
        while 1:
        
            # See if the response has arrived.
            for data in self.share_messages:
            
                if data[:4] == "R"+new_id:
                
                    print 'Successfully opened "%s"' % name
                    self.share_messages.remove(data)
                    return new_id
                
                elif data[:4] == "E"+new_id:
                
                    print 'Error: "%s"' % data[8:]
                    self.share_messages.remove(data)
                    return None



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
        
        # Maintain a dictionary of open shares and printers, and keep a
        # dictionary of events to use to communicate with them.
        self.shares = {}
        self.printers = {}
        self.share_events = {}
        self.printer_events = {}
    
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
            self.share_events[name].set()
            
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
        
            print "Share is already available: %s" % name
            return
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.share_events[name] = event
        
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
        
            print "Share is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.share_events[name].set()
        
        # Wait until the thread terminates.
        while self.shares[name].isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.shares[name]
        del self.share_events[name]
    
    def add_printer(self, name):
    
        """add_printer(self, name)
        
        Make the named printer available to other hosts.
        """
        
        if self.printers.has_key(name):
        
            print "Printer is already available: %s" % name
            return
        
        # Create an event to use to inform the share that it must be
        # removed.
        event = threading.Event()
        
        self.printer_events[name] = event
        
        # Create a thread to run the share broadcast loop.
        thread = threading.Thread(
            group = None, target = self.access.broadcast_printer,
            name = 'Printer "%s"' % name, args = (name, event),
            kwargs = {"protected": protected, "delay": delay}
            )
        
        self.printers[name] = thread
        
        # Start the thread.
        thread.start()
    
    def remove_printer(self, name):
    
        """remove_printer(self, name)
        
        Withdraw the named printer from service.
        """
        
        if not self.printers.has_key(name):
        
            print "Printer is not currently available: %s" % name
            return
        
        # Set the relevant event object's flag.
        self.printer_events[name].set()
        
        # Wait until the thread terminates.
        while self.printers[name].isAlive():
        
            pass
        
        # Remove the thread and the event from their respective dictionaries.
        del self.printers[name]
        del self.printer_events[name]
    
    def read_port(self, ports = [32770, 32771, 49171]):
    
        log = self.access.read_port(ports)
        
        return log
