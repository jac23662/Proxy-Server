#! /usr/bin/env python3

import socket
import threading
import sys
import os
import uuid
import json

HTTP_LEN = 3
log_arg = 2

do_log = False

thread_list = []

#TODO: https requests get stuck loading for some reason, try printing the data received
#from web_sock to see if there  is some sort of error response. Also saw piazza post about
#changing http 1.1 in the request to http 1.0, maybe that has something to do with it.
#need to add logging, and add the correct output for each connection


accept_clients = True

#processes the requests sent between a client and webserver
def process_client(cli_socket, addr, dolog):
    conn_active = True
    #recieves the incoming request from the client port
    request1 = cli_socket.recv(2048).decode(errors='ignore')
    #split request by line
    request = request1.split('\n')
    print(">>> " + request[0])
    #find the whitespace in host: [url]
    end_host = request[0].find(' ') + 1
    #url is everything after the whitespace
    url = request[0][end_host:]
    #retrieve info about the webserver from the url
    webserver, port = get_info(url)
    #create and connect a socket based on the info from the url
    web_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #attempt to connect to the web server
    try:
        web_sock.connect((webserver,port))
    except:
        #if it fails send a bad gateway message to client and close
        cli_socket.send("HTTP/1.1 502 Bad Gateway\r\n\r\n".encode())
        if dolog:
            log(request1, request, webserver, "HTTP/1.1 502 Bad Gateway\r\n\r\n")
        cli_socket.close()
        sys.exit()
    #if a connect request was received take steps for 
    if(is_connect(request[0])):
        request = '\n'.join(request)
        cli_socket.send("HTTP/1.1 200 OK\r\n\r\n".encode())
        #starts threads to handle the forwarding of client and webserver messages
        t1 = threading.Thread(target=forward_client, args=(cli_socket, web_sock))
        t1.start()
        t2 = threading.Thread(target=forward_server, args=(cli_socket, web_sock))
        t2.start()
        t1.join()
        t2.join()
        #close sockets before ending the client thread
        if dolog:
            log(request1, request, webserver, "HTTP/1.1 200 OK\r\n\r\n")
        cli_socket.close()
        web_sock.close()
        sys.exit()
    else:
        #if it is not a connect request forward the header
        request[0] = change_http(request[0])
        #rejoin the request into lines ending with \n after removing the keep-alives
        request = '\n'.join(filter_keep_alive(request))
        web_sock.sendall(request.encode())
        
    saveData = b''
    #send entire server response to the client
    while accept_clients:
        try:
            data = web_sock.recv(2048)
            if(len(data) > 0):
                saveData += data
                cli_socket.send(data)
            else:
                break
        except:
            pass
        
    if dolog:
        log(request1, request, webserver, saveData)
    cli_socket.close()
    web_sock.close()
    exit()

#checks to see if the received request is a CONNECT request
def is_connect(host_info):
    return host_info.find('CONNECT') != -1

#forwards all messages from the client to the web server
def forward_client(cli_socket,web_sock):
    cli_socket.setblocking(0)
    while(accept_clients):
        try:
            response = cli_socket.recv(2048)
            if(len(response) > 0):
                web_sock.send(response)
            else:
                break
        except:
            pass
#forwards all messages from the web server to the client
def forward_server(cli_socket, web_sock):
    web_sock.setblocking(0)
    while(accept_clients):
        try:
            response = web_sock.recv(2048)
            if(len(response) > 0):
                cli_socket.send(response)
            else:
                break
        except:
            pass

#removes the keep-alive connection and proxy connection lines
def filter_keep_alive(request):
    #iterate thru the lines and replace the keep-alive lines
    i = 0
    while(i < len(request)):
        if(request[i].find("Proxy-Connection:") != -1):
            request[i] = 'Proxy-connection: close'
        elif(request[i].find("Connection:") != -1):
            request[i] = 'Connection: close'
        i += 1
    return request

#Logs entries if Log is active
def log(header, modheader, webserver, data):
    #check if file is Connected or not
    is_conn = is_connect(header)
    dir_name = 'Log/' + 'www.' + webserver
    #make a directory if one doesn't exist
    try:
        # Create target Directory
        os.mkdir(dir_name)
    except FileExistsError:
        pass
        
    #build json file
    ID = str(uuid.uuid1())
    fileName = 'www.' + webserver + "." + ID + ".json"
    if not is_conn:
        libDict = { "Incoming header" : str(header), "Modified header" : str(modheader), "Server response received" : str(data.decode(errors='ignore'))}
    else:
        libDict = {"Incoming header" : str(header), "Proxy response sent" : str(data)}    
    jsonString = json.dumps(libDict, indent=4)
    jsonFile = open(dir_name + "/" + fileName, "w+")
    jsonFile.write(jsonString)
    jsonFile.close()

#replaces any instances of HTTP/1.1 with HTTP/1.1    
def change_http(host_info):
    host_info = host_info.split(' ')
    host_info[2] = "HTTP/1.0"
    return ' '.join(host_info)
    
    
#extract the hostname and port number from the url
def get_info(url):
    #finds the :// in the link
    start_pos = url.find('://')
    #checks to see if the url is an http or https url
    ishttps = False
    if(url[:start_pos] == 'https'):
        ishttps = True
    #if :// is present set url to the string starting immediately after the :// sequence
    if(start_pos != -1):
        start_pos += HTTP_LEN
        url = url[start_pos:]

    port = -1
    #port num will follow : if its present
    port_start = url.find(':')
    #if port is not explicitly written set it to default ports for http and https
    if(port_start == -1):
        if(ishttps):
            port = 443
        else:
            port = 80
    #if it is explicitly written parse the number up until the following whitespace
    else:
        end_of_port = url.find(' ')
        port = int(url[port_start+1:end_of_port])
        url = url[:end_of_port]

    #separates the server name from the rest of the url
    link_end = url.find('/')
    if(link_end != -1):
        #add one to remove the /
        link_end += 1
        servername = url[:link_end].split('/')[0]
    #if no / the name is everything up to the port
    else:
        servername = url[:port_start]
    return(servername, port)

#function that listens to keyboard input and waits for ctrl-d to initiate shutdown
def keyboard_interrupt():
    while(True):
        #take in input from keyboard
        try:
            keyboardinput = input()
        #ctrl-d was received, start shutdown
        except EOFError:
            #stop accepting clients and close incoming socket
            global accept_clients 
            global incoming
            incoming.close()
            accept_clients = False
            #iterate through threads and join them
            for t in thread_list:
                if(t is not threading.currentThread()):
                    t.join()
                    thread_list.remove(t)
            #once all threads have joined close the program
            sys.exit()


#ensure a port number was input for the proxy
if(len(sys.argv) <= 1):
    print("You need to input a port number for the proxy")
    sys.exit()
else:
    server_port = eval(sys.argv[1])

#check for log
if len(sys.argv) > 2:
    if sys.argv[log_arg] == 'Log':
        #print('yeh')
        do_log = True
        try:
            # Create target Directory
            os.mkdir('Log')
        except FileExistsError:
            pass
    else:
        print('Second Argument must be Log')
            

#creating the stream socket for incoming connections
incoming = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#allows for the socket to be reused
incoming.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

keyboard_t = threading.Thread(target=keyboard_interrupt)
keyboard_t.daemon = True
keyboard_t.start()
thread_list.append(keyboard_t)

#binding the socket to port 46103
incoming.bind((socket.gethostbyname(socket.gethostname()), server_port))

incoming.listen()

incoming.setblocking(0)

#listen for requests from browser
while(accept_clients):
    #accept the client and pass the info onto the process client method
    try:
        client_sock, client_addr = incoming.accept()
        
        #start a new thread for processing the new client
        t = threading.Thread(target=process_client, args=(client_sock, client_addr, do_log))
        t.start()
        thread_list.append(t)
    except:
        pass
sys.exit()
