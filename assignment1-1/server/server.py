import logging
import socket
import threading
import json
# import psycopg2
import sys
import pymongo

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Establish a connection to the MongoDB database
# conn = psycopg2.connect(dbname="", user="postgres", password="12345678", host="", port="5432")
# cur = conn.cursor()

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["btl-mmt"]

peers_collection = db["peers"]

def log_event(message):
    logging.info(message)

def update_client_info(peers_ip, peers_port, peers_hostname, file_name, file_size, piece_hash, piece_size, num_order_in_file):
    # Update the client's file list in the database
    for i in range(len(num_order_in_file)):
        data = {
            "peers_ip": peers_ip,
            "peers_port": peers_port,
            "peers_hostname": peers_hostname,
            "file_name": file_name,
            "file_size": file_size,
            "piece_hash": piece_hash[i],
            "piece_size": piece_size,
            "num_order_in_file": num_order_in_file[i]
        }
        peers_collection.insert_one(data)
        # cur.execute(
        #     "INSERT INTO peers (peers_ip,peers_port,peers_hostname,file_name,file_size,piece_hash,piece_size,num_order_in_file) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        #     (peers_ip,peers_port,peers_hostname,file_name,file_size,piece_hash[i],piece_size,num_order_in_file[i])
        # )
    # conn.commit()

active_connections = {}  
host_files = {}

def client_handler(conn, addr):
    try:

        while True:
            data = conn.recv(4096).decode()
            # log_event(f"Received data from {addr}: {data}")
            if not data:
                break

            command = json.loads(data)

            peers_ip = addr[0]
            peers_port = command['peers_port']
            peers_hostname = command['peers_hostname']
            file_name = command['file_name'] if 'file_name' in command else ""
            file_size = command['file_size'] if 'file_size' in command else ""
            piece_hash = command['piece_hash'] if 'piece_hash' in command else ""
            piece_size = command['piece_size'] if 'piece_size' in command else ""
            num_order_in_file = command['num_order_in_file'] if 'num_order_in_file' in command else ""

            if command.get('action') == 'introduce':
                client_peers_hostname = command.get('peers_hostname')
                active_connections[client_peers_hostname] = conn
                log_event(f"Connection established with {client_peers_hostname}/{peers_ip}:{peers_port})")

            elif command['action'] == 'publish':
                # peers_ip,peers_port,peers_hostname,file_name,piece_hash
                log_event(f"Updating client info in database for hostname: {peers_hostname}/{peers_ip}:{peers_port}")
                update_client_info(peers_ip,peers_port, peers_hostname,file_name,file_size, piece_hash,piece_size,num_order_in_file)  # addr[0] is the IP address
                log_event(f"Database update complete for hostname: {peers_hostname}/{peers_ip}:{peers_port}")
                conn.sendall("File list updated successfully.".encode())

            elif command['action'] == 'fetch':
                print("fetch", file_name, num_order_in_file, piece_hash)
                # Query the database for the IP addresses of the clients that have the file

                # cur.execute("SELECT * FROM peers WHERE file_name = %s AND num_order_in_file <> ALL (%s) AND piece_hash <> ALL (%s)", (file_name, num_order_in_file, piece_hash))
                # results = cur.fetchall()
                query = {
                    "file_name": file_name,
                    "$nor": [
                        {"num_order_in_file": {"$in": num_order_in_file}},
                        {"piece_hash": {"$in": piece_hash}}
                    ]
                }
                # Execute the query and fetch results
                results = list(peers_collection.find(query))
                
                if results:
                    # Create a list of dictionaries with 'hostname' and 'ip' keys

                    peers_info = [
                        {
                            'peers_ip': result["peers_ip"], 
                            'peers_port': result["peers_port"], 
                            'peers_hostname': result["peers_hostname"], 
                            'file_name': result["file_name"],
                            'file_size': result["file_size"],
                            'piece_hash': result["piece_hash"],
                            'piece_size': result["piece_size"],
                            'num_order_in_file': result["num_order_in_file"]
                        } 
                        for result in results if result["peers_hostname"] in active_connections
                    ]
                    print(peers_info)
                    conn.sendall(json.dumps({'peers_info': peers_info}).encode())
                else:
                    conn.sendall(json.dumps({'error': 'File not available'}).encode())

            elif command['action'] == 'file_list':
                files = command['files']
                print(f"List of files : {files}")

    except Exception as e:
        logging.exception(f"An error occurred while handling client {addr}: {e}")
    finally:
        if client_peers_hostname:
            del active_connections[client_peers_hostname]  
        conn.close()
        log_event(f"Connection with {addr} has been closed.")

def request_file_list_from_client(peers_hostname):
    if peers_hostname in active_connections:
        conn = active_connections[peers_hostname]
        print(active_connections[peers_hostname])
        ip_address, _ = conn.getpeername()
        # print(ip_address)
        peer_port = 65433  
        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.connect((ip_address, peer_port))
        request = {'action': 'request_file_list'}
        peer_sock.sendall(json.dumps(request).encode() + b'\n')
        response = json.loads(peer_sock.recv(4096).decode())
        peer_sock.close()
        if 'files' in response:
            return response['files']
        else:
            return "Error: No file list in response"
    else:
        return "Error: Client not connected"

def discover_files(peers_hostname):
    # Connect to the client and request the file list
    files = request_file_list_from_client(peers_hostname)
    print(f"Files on {peers_hostname}: {files}")

def ping_host(peers_hostname):
    # cur.execute("SELECT address FROM client_files WHERE hostname = %s", (peers_hostname,))
    # results = cur.fetchone()  

    # Construct the MongoDB query
    query = {"hostname": peers_hostname}

    # Execute the query and fetch the result
    results = peers_collection.find_one(query)

    ip_address = results[0]
    print(ip_address)
    if ip_address:
        peer_port = 65433
        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.connect((ip_address, peer_port))
        request = {'action': 'ping'}
        peer_sock.sendall(json.dumps(request).encode() + b'\n')
        response = peer_sock.recv(4096).decode()
        peer_sock.close()
        if response:
            print(f"{peers_hostname} is online!")
        else:
            print(f"{peers_hostname} is offline!")
    else:
        print("There is no host with that name")



def server_command_shell():
    while True:
        cmd_input = input("Server command: ")
        cmd_parts = cmd_input.split()
        if cmd_parts:
            action = cmd_parts[0]
            if action == "discover" and len(cmd_parts) == 2:
                hostname = cmd_parts[1]
                thread = threading.Thread(target=discover_files, args=(hostname,))
                thread.start()
            elif action == "ping" and len(cmd_parts) == 2:
                hostname = cmd_parts[1]
                thread = threading.Thread(target=ping_host, args=(hostname,))
                thread.start()
            elif action == "exit":
                break
            else:
                print("Unknown command or incorrect usage.")

def start_server(host='0.0.0.0', port=65432):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen()
    log_event("Server started and is listening for connections.")

    try:
        while True:
            conn, addr = server_socket.accept()
            # host = server_socket.getsockname()
            log_event(f"Accepted connection from {addr}, hostname is {host}")
            thread = threading.Thread(target=client_handler, args=(conn, addr))
            thread.start()
            log_event(f"Active connections: {threading.active_count() - 1}")

    except KeyboardInterrupt:
        log_event("Server shutdown requested.")

    finally:
        server_socket.close()
        # cur.close()
        conn.close()

if __name__ == "__main__":
    
    SERVER_PORT = 65432
    SERVER_HOST='localhost'
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(SERVER_HOST, SERVER_PORT))
    server_thread.start()

    # Start the server command shell in the main thread
    server_command_shell()

    # Signal the server to shutdown
    print("Server shutdown requested.")
    
    sys.exit(0)