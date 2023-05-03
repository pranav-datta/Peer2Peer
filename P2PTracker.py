import socket
import threading
import custom_logger


class P2PTracker:
    def __init__(self):
        self.check_list = {}
        self.chunk_list = {}
        self.ip = 'localhost'
        self.port = 5100
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger = custom_logger.CustomLogger().logger

    def start(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        while True:
            client_socket, client_address = self.socket.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()

    def handle_client(self, client_socket):
        while True:
            request = client_socket.recv(1024).decode().strip()
            command, *args = request.split(',')
            if command == "LOCAL_CHUNKS":
                self.handle_local_chunks(*args)
            elif command == "WHERE_CHUNK":
                self.handle_where_chunk(*args, client_socket)

    def handle_local_chunks(self, chunk_index, file_hash, ip_address, port_number):
        #self.logger.info(f'{client_name},LOCAL_CHUNKS,{chunk_index},{file_hash},{ip_address},{port_number}')
        #Also do this ^^ log client side
        # General Logic of this:
        # If it is already in the checklist -> loop through and see if one has the same hash
        # 	If they do not -> add this one to the checklist as well
        #		If one does match -> if its already in the chunk list then append the ip and port
        #												 if not add a base list
        entry = (file_hash, ip_address, port_number)
        if chunk_index in self.check_list:
            for check_entry in self.check_list[chunk_index]:
                if check_entry[0] == entry[0]: #Compare hash
                    if chunk_index not in self.chunk_list:
                        self.chunk_list[chunk_index] = [entry]
                        self.chunk_list[chunk_index].append(check_entry)
                    else:
                        self.chunk_list[chunk_index].append(entry)
                    #self.logger.info("Added entry to chunk_list: ({}, {}, {}, {})".format(chunk_index, *entry))
                    break
            self.check_list[chunk_index].append(entry)
            #self.logger.info("Added entry to check_list: ({}, {}, {}, {})".format(chunk_index, *entry))
        else:
            self.check_list[chunk_index] = [entry]
            #self.logger.info("Added entry to check_list: ({}, {}, {}, {})".format(chunk_index, *entry))

    def handle_where_chunk(self, chunk_index, client_socket):
        #self.logger.info(f'{client_name},WHERE_CHUNK,{chunk_index}')
        # ^ put this on client side I think
        response = f"CHUNK_LOCATION_UNKNOWN,{chunk_index}"
        if chunk_index in self.chunk_list:
            entries = self.chunk_list[chunk_index]
            response = f"GET_CHUNK_FROM,{chunk_index},{entries[0][0]}"
            for entry in entries:
                response += f',{entry[1]},{entry[2]}'
        client_socket.send(response.encode())
        self.logger.info(f'P2PTracker,{response}')


if __name__ == "__main__":
    t = P2PTracker()
    t.start()