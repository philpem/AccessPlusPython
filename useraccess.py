#!/usr/bin/env python

"""
useraccess.py

Administration tool and Access+ peer.

Serve local pages only.
"""

import access, SimpleHTTPServer, string, sys, os, socket, urllib


__version__ = "0.1"


standard_error_page = \
"""<html>
<head>
  <title>404 - Not Found</title>
</head>

<body>
  <h1>404 - Not Found</h1>
  <p>
    The page you requested could not be found.
  </p>
</body>
</html>
"""


class Request:

    pass

class GetResource(Request):

    def __init__(self, path):
    
        self.path = path

class ListResources(Request):

    def __init__(self, path):
    
        self.path = path


class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    server_version = "Server/" + __version__
    
    def handle(self):
    
        SimpleHTTPServer.SimpleHTTPRequestHandler.handle(self)
    
    def do_GET(self):
        """Serve a GET request."""
        
        # Translate the path passed by the client into a request for
        # information.
        request = self.translate_path(self.path)
        
        # The server holds the states of all the clients, so ask the server
        # to return the information. The returned value is a tuple containing
        # the content type and the data.
        content_type, data = self.perform_request(request)
        
        # Ensure that the headers are set correctly for this page and send
        # the data to the client.
        self.send_head(content_type, data)

    def do_HEAD(self):
        """Serve a HEAD request."""
        
        # Translate the path passed by the client into a request for
        # information.
        request = self.translate_path(self.path)
        
        # The server holds the states of all the clients, so ask the server
        # to return the information. The returned value is a tuple containing
        # the content type and the data.
        content_type, data = self.perform_request(request)
        
        # Ensure that the headers are set correctly for this page.
        self.send_head(content_type)
    
    #def do_POST(self):
    #    """Serve a POST request."""
    
    # Modified version of send_head from SimpleHTTPRequestHandler
    
    def send_head(self, content_type, data = None):
    
        """send_head(self, content_type)
        \r
        \rCommon code for GET and HEAD commands.
        \r
        \rThis sends the response code and ME headers.
        """
        
        if content_type == None:
        
            #self.send_error(404, "File not found")
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("")
            return
        
        # Send the ME headers.
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
        
        if data != None:
        
            # Write the data to the output file.
            self.wfile.write(data)
    
    def translate_path(self, path):
    
        """translate_path(self, path)
        \r
        \rTranslate the path given into a request object.
        """
        
        if string.find(path, "/") != -1:
        
            # A reference to a resource.
            
            # Create a list of directory names without any empty strings.
            path = filter(lambda x: x != "", string.split(path, "/"))
            
            # Return a request to get the resource.
            return GetResource(path)
        
        else:
        
            return None
    
    def perform_request(self, request):
    
        if request:
        
            # Ask the server to perform the request.
            return server.perform_request(self.client_address[0], request)
        
        else:
        
            # No request to send.
            return (None, None)



class Server(SimpleHTTPServer.BaseHTTPServer.HTTPServer):

    def __init__(self, addr, port = 8000, accept = None):
    
        # Start the server using the HTTPServer class we inherit from.
        # The server address and port are stored in server_name and
        # server_port.
        
        SimpleHTTPServer.BaseHTTPServer.HTTPServer.__init__(
            self, (addr, port), RequestHandler
            )
        
        # Access control
        self.accept_addresses = accept
    
    def accept_request(self, client):
    
        if self.accept_addresses == None:
        
            # All addresses are accepted.
            return 1
        
        # Look up the client host name.
        client_addr = socket.gethostbyaddr(client)
        
        for addr in client_addr:
        
            if addr in self.accept_addresses:
            
                # If a match was successful then return immediately.
                return 1
        
        # The client address failed to match with any of the allowed addresses.
        return 0
    
    def perform_request(self, client_address, request):
    
        # Simple access control
        if not self.accept_request(client_address):
        
            # Not a valid request.
            return (None, None)
        
        # Perform a request on behalf of the request handler.
        
        if not isinstance(request, Request):
        
            # Not a valid request.
            return (None, None)
        
        elif isinstance(request, GetResource):
        
            # Use the path given. *** Very dodgy. ***
            path = string.join(request.path, os.sep)
            
            if os.path.isdir(path):
            
                # Look for an index file.
                path = os.path.join(path, "index.html")
            
            try:
            
                return ( "text/html", open(path, "r").read() )
            
            except IOError:
            
                # Return a 404 (Not Found) error.
                #return (None, None)
                
                # Return a valid page.
                return (None, standard_error_page)
        
        # Not a valid request.
        return (None, None)



if __name__ == "__main__":

    # Only accept requests from the local host.
    accept = [access.Hostaddr]
    
    # Create a server instance.
    server = Server(
        socket.gethostbyname(access.Hostaddr), accept = accept
        )
    
    # Start the server.
    server.serve_forever()
    
    # Exit
    sys.exit()
