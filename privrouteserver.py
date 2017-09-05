#! /bin/env python3

# This application gets information about connected openvpn clients and replaces
# routes in the main routing table accordingly. The user certificate's CN is used to find its routes, basically authenticating it. However, that authentication
# happens in openvpn and hence is spoofable here. You are encouraged to use iptables to restrict access to it.

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
#   "SourceIP" : If set to anything other than None, the source IP of the route
# }

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class privilegedRouteSetter():
    context=None
    socket=None

    lookupTable={
        "centos-gw" : [ ipaddress.IPv4Network("192.168.178.0/24") ]
    }
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def validateFormat(self, message : dict):
        lst=[ "DN", "Interface" ]
        for i in message.keys():
            try:
                lst.remove(i)
            except:
                pass
            if not i.isalnum():
                return False
        if len(lst) != 0:
            return False
        return True

    def addRoute(self, network : ipaddress.IPv4Network, interface : str = None, nextHop : str = None):
        args="/usr/bin/ip route replace {} dev {}".format(network, interface)
        if nextHop != None:
            args+=" via {}".format(nextHop)

        print ("Args: "+ str(args))
        p=subprocess.Popen(args.split(" "))
        p.wait()
        if p.returncode != 0:
            return False
        return True

    def sendFormatError(self):
        self.socket.send_string(json.dumps({ "Status" : "False", "Error" : "Format error" }))

    def sendNoRoutesError(self):
        self.socket.send_string(json.dumps({ "Status" : "False", "Error" : "No routes for that DN" }))

    def sendUnknownUserError(self):
        self.socket.send_string(json.dumps({ "Status" : "False", "Error" : "No such user known" }))

    def sendSuccess(self):
        self.socket.send_string(json.dumps({ "Status" : "True"}))

    def sendProcessError(self):
        self.socket.send_string(json.dumps({ "Status" : "False", "Error" : "An error occured while trying to add the routes."}))

    def handleConnection(self, message):
        try:
            parsed=json.loads(message)
        except:
            self.sendFormatError()
        else:
            if not self.validateFormat(parsed):
                self.sendFormatError()
                return
            DN = parsed.get("DN")
            if DN != None:
                networks = self.lookupTable.get(DN)
                if networks != None:
                    for i in networks:
                        if self.addRoute(network=i, interface=parsed["Interface"], nextHop=parsed["NextHop"]):
                            self.sendSuccess()
                        else:
                            self.sendProcessError()
                else:
                    self.sendNoRoutesError()
            else:
                self.sendUnknownUserError()


    def run(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://{}:{}".format(self.ip, self.port))
        while True:
            message = self.socket.recv()
            eprint("Received message {}".format(message))
            self.handleConnection(message)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Handles request for route installations from unprivileged processes.")
    parser.add_argument("-s", "--ip",
        help="Sets the IP the process should listen on",
        dest="ip",
        nargs = "?",
        default = "127.0.0.1"
        )
    parser.add_argument("-p", "--port",
        help="Sets the TCP port the process should listen on",
        dest="port",
        nargs = "?",
        default = "6001"
        )
    args = parser.parse_args()

    privRouteSetter = privilegedRouteSetter(args.ip, args.port)
    privRouteSetter.run()