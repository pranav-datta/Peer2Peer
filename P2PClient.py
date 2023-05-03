import socket
import argparse
import threading
import hashlib
import custom_logger
import random
import time


def handle_where(msg):
    msg = msg.replace("'", "")
    split = msg.split(",")
    num_clients = int((len(split) - 3) / 2)
    if (split[0] == "CHUNK_LOCATION_UNKNOWN") or num_clients < 1:
        return -1, -1
    client_to_connect = random.randint(0, num_clients - 1)
    return split[3 + (2 * client_to_connect)], int(split[4 + (2 * client_to_connect)])
    # returns (-1, -1) if chunk location unknown


class P2PClient:

    def __init__(self, folder, port, name):
        # Important global variables
        self.folderPath = folder
        self.transferPort = int(port)
        self.name = name
        self.connections = {}
        self.missing_chunks = []
        self.chunk_indices = []
        self.chunks = []
        self.hashes = []
        self.num_chunk = 0
        #Customer Logger
        self.logger = custom_logger.CustomLogger().logger


    def connect_to_others(self, cname, ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        #self.logger.info(f"{self.name},CONNECTED_TO,{ip},{port}")
        self.connections[cname] = sock

    def read_file(self):
        f = open(self.folderPath + "/local_chunks.txt", "r")
        for line in f:
            split = line.split(",")
            if split[1].strip() == "LASTCHUNK":
                self.num_chunk = int(split[0])
            else:
                self.chunk_indices.append(int(split[0]))
                self.chunks.append(split[1].strip())
        for i in range(self.num_chunk):
            index = i+1
            if index not in self.chunk_indices:
                self.missing_chunks.append(index)
        #self.logger.info(f"{self.name},READ,{self.num_chunk},{self.missing_chunks}")

    def compute_hashes(self):
        self.hashes = []
        for chunk in self.chunks:
            h = hashlib.sha1()
            with open(self.folderPath + "/" + chunk, 'rb') as file:
                while True:
                    c = file.read(1024)
                    if not c:
                        break
                    h.update(c)
            result = h.hexdigest()
            #self.logger.info(f"{self.name},HASHING,{chunk},AS,{result}")
            self.hashes.append(result)

    def send_chunks_to_tracker(self, hashes):
        ip = 'localhost'
        trackSocket = self.connections['p2ptracker']
        for i, h in zip(self.chunk_indices, hashes):
            msg = f"LOCAL_CHUNKS,{i},{h},{ip},{self.transferPort}"
            trackSocket.send(msg.encode())
            self.logger.info(f'{self.name},{msg}')
            time.sleep(0.1)

    def handle_request(self, sock):
        msg = sock.recv(1024).decode()
        #msg = msg.replace("'", "")
        split = msg.split(",")
        index = int(split[1])
        chunk_index = self.chunk_indices.index(index)
        chunk = self.chunks[chunk_index]
        #self.logger.info(f"{self.name},HANDLING_REQUEST,{chunk}")
        file = open(self.folderPath + "/" + chunk, 'rb')
        sock.send(chunk.encode('utf-8'))
        name_confirmation = sock.recv(2048).decode('utf-8')
        time.sleep(0.1)
        """
        contents = file.read(4096)
        while contents:
            #self.logger.info(f"{self.name},SENT,{contents}")
            sock.send(contents)
            contents = file.read(4096)
            time.sleep(0.1)
        """
        sock.sendfile(file)
        time.sleep(0.1)
        sock.send(b"DONE")
        file_confirmation = sock.recv(2048).decode('utf-8')
        sock.shutdown(socket.SHUT_WR)
        sock.close()

    def request_client(self, client_ip, client_port, chunk_index):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((client_ip, client_port))
        msg = f"REQUEST_CHUNK,{chunk_index}"
        s.send(msg.encode())
        self.logger.info(f"{self.name},{msg},{client_ip},{client_port}")
        time.sleep(0.1)
        fileName = s.recv(2048).decode('utf-8')
        s.send("Received filename".encode('utf-8'))
        time.sleep(0.1)
        f = open((self.folderPath + "/" + fileName), 'wb')
        while True:
            #self.logger.info(f"{self.name},RECEIVED,{piece}")
            piece = s.recv(8192)
            if (piece == b"DONE"):
                break
            f.write(piece)
        f.close()
        s.send("Received file".encode('utf-8'))
        s.shutdown(socket.SHUT_WR)
        s.close()
        time.sleep(0.1)
        self.chunks.append(fileName)
        self.chunk_indices.append(chunk_index)
        self.compute_hashes()
        trackSocket = self.connections['p2ptracker']
        msg = f"LOCAL_CHUNKS,{chunk_index},{self.hashes[-1]},{'localhost'},{self.transferPort}"
        trackSocket.send(msg.encode())
        self.logger.info(f"{self.name},{msg}")
        self.missing_chunks.remove(chunk_index)

    def ask_where(self):
        trackSocket = self.connections['p2ptracker']
        msg = f"WHERE_CHUNK,{self.missing_chunks[0]}"
        self.logger.info(f"{self.name},{msg}")
        trackSocket.send(msg.encode())
        time.sleep(1)
        resp = trackSocket.recv(2048).decode()
        ip, port = handle_where(resp)
        if ip == -1 and port == -1:
            self.missing_chunks = self.missing_chunks[1:] + [self.missing_chunks[0]]
            return
        self.request_client(ip, port, self.missing_chunks[0])

    def start_listening(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', self.transferPort))
        sock.listen()
        while True:
            client_socket, client_address = sock.accept()
            client_thread = threading.Thread(target=self.handle_request, args=(client_socket,))
            client_thread.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Client')
    parser.add_argument('-folder')
    parser.add_argument('-transfer_port')
    parser.add_argument('-name')
    args = parser.parse_args()
    client = P2PClient(args.folder, args.transfer_port, args.name)
    # Connect to P2PTracker++
    client.connect_to_others('p2ptracker', 'localhost', 5100)
    client.read_file()
    client.compute_hashes()
    client.send_chunks_to_tracker(client.hashes)
    recv_thread = threading.Thread(target=client.start_listening)
    recv_thread.start()
    while len(client.missing_chunks) > 0:
        time.sleep(0.1)
        client.ask_where()
