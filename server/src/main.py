import socketserver

from src import server


def run():
    HOST, PORT = "localhost", 9090

    # Create the server, binding to localhost on port 9090
    myserver = socketserver.ThreadingTCPServer((HOST, PORT), server.MyTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    myserver.serve_forever()
