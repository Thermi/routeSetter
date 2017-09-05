#! /bin/env python3

# This application gets contacts the system's privileged route setter and asks it to add routes to the main routing table for a given DN.
# The DNs are mapped to the belonging routes. Routes can not be specified client side.

import argparse
import ipaddress
import json
import os
import subprocess
import sys
import zmq


# expected format:
# {
#   "DN" : The DN of the certificate in UTF-8 encoding
#   "Interface" : The name of the interface that the route needs to use
#   "NextHop" : If set to anything other than None, the next hop
# }

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class privRouteClient():

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def formatMessage(self):
        return {
            "DN" : os.environ.get("common_name"),
            "Interface" : os.environ.get("dev"),
            "NextHop" : os.environ.get("route_gateway")
        }

    def validateFormat(self, message):
        if message.get("Status") == None:
            return False
        return True

    def sendMessage(self, message):
        self.socket.send_string(json.dumps(message))

    def handleReply(self, reply):
        parsed=json.loads(reply)
        if not self.validateFormat(parsed):
            eprint("Incorrect reply received: {}".format(parsed))
            return
        else:
            {
                "True" : lambda : eprint("Successfully added routes."),
                "False" : lambda : eprint ("An error occured when trying to add the routes: {}".format(parsed["Error"])),
            }.get(parsed["Status"], lambda parsed : eprint("Incorrect Status received: {}".format(parsed["Status"])))()

    def run(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://{}:{}".format(self.ip, self.port))
        self.sendMessage(self.formatMessage())
        self.handleReply(self.socket.recv())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Contacts a given privRouteSetter process and asks it to add routes for the given DN.")
    parser.add_argument("-s", "--ip",
        help="Sets the IP the client should connect to",
        dest="ip",
        nargs = "?",
        default = "127.0.0.1"
        )
    parser.add_argument("-p", "--port",
        help="Sets the TCP port the client should connect to",
        dest="port",
        nargs = "?",
        default = "6001"
        )
    args = parser.parse_args()
    pClient = privRouteClient(args.ip, args.port)
    pClient.run()