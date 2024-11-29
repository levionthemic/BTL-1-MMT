import socket
import os
import bencodepy
import threading
import sys
import transform
import requests
import hashlib
import math
import subprocess
from urllib.request import urlopen
import re

class Peer:
    def __init__(self):
        self.listen_socket = None 
        self.port = None
        self.bytes = 0
        self.file_path = []
    
    def find_empty_port(self, start_port=6881, end_port=65535):
        for port in range(start_port, end_port + 1):
            try:
                # Thử bind socket đến cổng được chỉ định
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((get_local_ip(), port))
                # Nếu không có ngoại lệ xảy ra, cổng này không được sử dụng
                return port
            except OSError:
                # Cổng đã được sử dụng, thử cổng tiếp theo
                continue
        # Không tìm thấy cổng trống trong phạm vi được chỉ định
        return None

    def write_string_to_file(self, string):
        file_name = f"info_{self.port}.txt"
        file_dir = "peer_directory"
        file_path = os.path.join(file_dir, file_name)

        # Tạo thư mục nếu chưa tồn tại
        os.makedirs(file_dir, exist_ok=True)  

        # Đảm bảo chỉ ghi một chuỗi vào mỗi hàng
        unique_strings = set()

        # Đọc dữ liệu từ file để kiểm tra chuỗi trùng lặp
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    unique_strings.add(line.strip())
        except FileNotFoundError:
            pass  # Bỏ qua lỗi nếu file không tồn tại

        # Thêm chuỗi mới vào tập hợp
        unique_strings.add(string)

        # Ghi các chuỗi vào file
        with open(file_path, 'w') as file:
            for unique_string in unique_strings:
                file.write(unique_string + '\n')
    

    def create_torrent_file(self, file_path, file_dir, tracker_url):
        """
        Hàm tạo file torrent của 1 file.
        
        Args:
            file_path (string): Đường dẫn tuyệt đối đến file muốn tạo torrent.
            file_dir (string): Đường dẫn đến thư mục lưu file torrent.
            tracker_url (string) Địa chỉ HTTP của tracker.
        """

        file_name = os.path.basename(file_path)

        # Ghi thông tin đường dẫn file muốn tạo torrent vào folder peer_directory
        self.write_string_to_file(file_path)

        print(f"Creating torrent file for {file_name}...")

        # Thực hiện tạo file torrent
        transform.create_torrent(
            file_path, 
            tracker_url, 
            os.path.join(file_dir, f'{file_name}.torrent')
        )


    def upload_torrent_file(self, torrent_file_path, tracker_url):
        """
        Hàm xử lý upload file torrent.
        
        Args:
            torrent_file_path (string): Đường dẫn đến file torrent.
            tracker_url (string): Địa chỉ HTTP của tracker.
        """

        try:
            # Đọc dữ liệu từ file torrent
            with open(torrent_file_path, 'rb') as torrent_file:
                torrent_data = torrent_file.read()
            
            # Tạo mã băm
            info_hash = str(hashlib.sha1(torrent_data).hexdigest())

            try:
                # Gửi một HTTP GET lên tracker với info_hash là param
                url_get = f'http://{tracker_url}:8080/announce/upload?info_hash=${info_hash}&port={self.port}'
                response = requests.get(url_get)

                if response.status_code == 200:
                    print("Upload to tracker successfully.")
                else:
                    print("Failed to upload to tracker. Status code:", response.status_code)

            except Exception as e:
                print("Error connecting to tracker:", e)

        except Exception as e:
            print(f"Error uploading torrent file: {e}")


    def download_torrent_file(self, torrent_file_path, download_dir):
        """
        Hàm xử lý download file thông qua file torrent.
        
        Args:
            torrent_file_path (string): Đường dẫn đến file torrent.
            download_dir (string): Đường dẫn đến thư mục chứa file tải về.
        """

        # Tạo folder download_dir 
        os.makedirs(download_dir, exist_ok=True)
      
        # Lấy tên file torrent
        torrent_file_name = os.path.basename(torrent_file_path)

        # Tách phần tên tệp ra khỏi phần mở rộng 
        # ví dụ: 'Data.pdf.torrent' => 'Data.pdf'
        file_name_without_extension = os.path.splitext(torrent_file_name)[0]

        # Kết hợp đường dẫn của thư mục chứa file tải về với tên tệp 
        # ví dụ: '/download/Data.pdf'
        dest_file_path = os.path.join(download_dir, file_name_without_extension)
        try:
            with open(torrent_file_path, 'rb') as torrent_file:
                torrent_data = torrent_file.read()
            
            decoded_torrent = bencodepy.decode(torrent_data)
            
            info_hash = str(hashlib.sha1(torrent_data).hexdigest())
            tracker_url = decoded_torrent[b"announce"].decode()
                
            try:
                url_get = f'http://{tracker_url}:8080/announce/download?info_hash={info_hash}'
                response = requests.get(url_get)
             
                # Kiểm tra mã trạng thái của phản hồi
                if response.status_code == 200:

                    # Lấy tất cả các cặp (ip, port) tương ứng với info_hash
                    # Các cặp (ip, port) này đại diện cho các peer đang chia sẻ file torrent chứa info_hash tương ứng
                    ip_port_pairs = response.text.split(",")

                    # Duyệt qua từng cặp (ip, port)
                    formatted_ip_addresses = []
                    for pair in ip_port_pairs:
                        ip, port = pair.strip().split(":")

                        # Không xét trên peer hiện tại
                        if port != self.port:
                            formatted_ip_addresses.append((ip, int(port)))

                    print("Formatted IP addresses:", formatted_ip_addresses)

                    threads = []
                    decoded_str_keys = {
                        transform.bytes_to_str(k): v 
                        for k, v in decoded_torrent.items()
                    }
                    total_pieces = math.ceil(
                        decoded_str_keys["info"][b"length"] /
                        decoded_str_keys["info"][b"piece length"]
                    )
                    print(f"Total pieces: {total_pieces}")

                    pieces_per_thread = total_pieces // len(formatted_ip_addresses) + 1
                    print(f"Pieces per thread: {pieces_per_thread}")

                    # Lặp qua mỗi piece thuộc cửa sổ [start_piece, end_piece]
                    start_piece = 0
                    for ip_address in formatted_ip_addresses:
                        end_piece = start_piece + pieces_per_thread
                        if end_piece > total_pieces:
                            end_piece = total_pieces
                        
                        # Tạo 1 luồng tải về 1 piece [start_piece, end_piece]
                        thread = threading.Thread(
                            target=self.download_range, 
                            args=(
                                ip_address, torrent_data, dest_file_path, 
                                start_piece, end_piece, 
                                tracker_url, total_pieces
                            )
                        )
                        threads.append(thread)
                        start_piece = end_piece
                        thread.start()

                    # Chờ cho các luồng tải các piece
                    for thread in threads:
                        thread.join()

                else:
                    print("Error:", response.status_code)

            except Exception as e:
                print(f"Error connecting to tracker: {e}")

        except Exception as e:
            print(f"Error downloading torrent file: {e}")

    def download_range(
            self, 
            ip_address, torrent_data, dest_file_path, 
            start_piece, end_piece, 
            tracker_url, total_pieces
    ):
        for piece in range(start_piece, end_piece):
            self.download_piece(
                ip_address, torrent_data, dest_file_path, 
                str(piece), tracker_url, 
                total_pieces
            )

    def download_piece(
            self, 
            ip_address, torrent_data, dest_file_path, 
            piece, tracker_url, 
            total_pieces
    ):
        peer_ip, peer_port = ip_address
        
        # Tạo 1 socket kết nối tới peer đang chia sẻ file cần tải
        sock = socket.create_connection((peer_ip, peer_port))
        
        info_hash = str(hashlib.sha1(torrent_data).hexdigest())
        payload = info_hash + " " + tracker_url
        sock.sendall(payload.encode('utf-8'))
        
        response = sock.recv(1024).decode('utf-8')

        if response == "OK":

            # Gửi 1 thông điệp interested thông báo muốn tải dữ liệu
            interested_payload = (2).to_bytes(4, "big") + (2).to_bytes(1, "big")
            sock.send(interested_payload)

            # Nhận thông điệp unchoke
            unchoke_msg = sock.recv(5)
            print(f"Received unchoke message from {ip_address}: {unchoke_msg}")
            message_length, message_id = self.parse_peer_message(unchoke_msg)
            if message_id != 1:
                raise SystemError("Expecting unchoke id of 1")

            decoded_torrent = bencodepy.decode(torrent_data)
            decoded_str_keys = {
                transform.bytes_to_str(k): v 
                for k, v in decoded_torrent.items()
            }
            
            # Chia nhỏ piece thành các block và gửi request cho từng block

            bit_size = 16 * 1024 # Kích thước 1 block (16 KB)
            final_block = b""

            piece_length = decoded_str_keys["info"][b"piece length"]
            total_length = decoded_str_keys["info"][b"length"]

            # Nếu là piece cuối, lấy phần dư còn lại làm độ dài piece
            if int(piece) == math.ceil(total_length / piece_length) - 1:
                piece_length = total_length % piece_length
            
            # Tạo tên tệp tạm thời dựa trên index của piece
            piece_filename = f"{dest_file_path}_piece_{piece}"
            
            # Lặp qua từng block trong 1 piece
            # Offset là vị trí bắt đầu của 1 block
            for offset in range(0, piece_length, bit_size):
                '''
                    Gửi yêu cầu tải block (message ID = 6) qua socket
                '''
                # Độ dài block trong 1 piece
                block_length = min(bit_size, piece_length - offset)

                request_data = (
                    int(piece).to_bytes(4, "big") # Piece index (4 bytes)
                    + offset.to_bytes(4, "big") # Offset trong piece (4 bytes)
                    + block_length.to_bytes(4, "big") # Kích thước block (4 bytes)
                )
                request_payload = (
                    (len(request_data) + 1).to_bytes(4, "big") # Tổng độ dài payload (4 bytes)
                    + (6).to_bytes(1, "big") # Message ID (1 byte, "request" = 6)
                    + request_data
                )
                sock.send(request_payload)

                '''
                    Nhận phản hồi từ peer (message ID = 7) và xác minh dữ liệu.
                '''
                message_length = int.from_bytes(sock.recv(4), "big") # Độ dài thông điệp (4 bytes)
                message_id = int.from_bytes(sock.recv(1), "big") # ID thông điệp (1 byte)
                
                if message_id != 7:
                    raise SystemError("Expecting piece id of 7")
                
                piece_index = int.from_bytes(sock.recv(4), "big") # Index của piece
                begin = int.from_bytes(sock.recv(4), "big")  # Offset của block trong piece
                received = 0
                full_block = b""
                size_of_block = message_length - 9 # Tổng độ dài phản hồi trừ đi: 4 byte (piece index), 4 byte (begin offset), 1 byte (message ID).
                # Lặp lại cho đến khi toàn bộ block được nhận.
                while received < size_of_block:
                    block = sock.recv(size_of_block - received) # Nhận dữ liệu block
                    full_block += block
                    received += len(block)
                final_block += full_block # Ghi dữ liệu vào final_block

                print(f"Downloading piece {piece}, offset {offset}, block length {block_length} from {ip_address}")
        
        try:
            # Lưu dữ liệu của piece vào tệp tạm thời
            with open(piece_filename, "wb") as f:
                f.write(final_block)

        except Exception as e:
            print(e)

        # Kiểm tra xem tất cả các phần đã được tải xong chưa
        downloaded_pieces = [f"{dest_file_path}_piece_{piece}" for piece in range(total_pieces)]
        d = len(list(piece_file for piece_file in downloaded_pieces if os.path.exists(piece_file)))

        print(f"Downloaded {d} pieces out of {len(downloaded_pieces)}")
        if all(os.path.exists(piece_file) for piece_file in downloaded_pieces):
            self.merge_temp_files(dest_file_path, math.ceil(total_length / piece_length))
            self.bytes += total_length  # Cập nhật số byte đã tải
            print("Download completed.")


    def handle_peer_request(self, client_socket, client_address):
        try:
            # Nhận dữ liệu từ peer
            data = client_socket.recv(1024)  # Nhận tối đa 1024 bytes
            print(f"Received data from {client_address}: {data}")

            if data is not None:
                decoded_data = data.decode('utf-8')  # Chuyển đổi byte string thành string thông thường
                parts = decoded_data.split(' ', 1)
                if len(parts) == 2:
                    data, url = parts
                    print(f"Data: {data}")
                    print(f"URL: {url}")
                
                # Tìm file tương ứng với thông tin hash nhận được
                found_files = self.find_file_by_infohash(data, url)
                print("Found files:", found_files)
                if found_files:
                    # Gửi phản hồi OK nếu peer có file
                    client_socket.sendall(b"OK")
                    # Nhận phản hồi từ peer
                    response = client_socket.recv(1024).decode()
                    unchoke_payload = self.create_unchoke_message()
                    client_socket.sendall(unchoke_payload)

                    while True:
                        # Nhận dữ liệu yêu cầu từ peer
                        request_length = int.from_bytes(client_socket.recv(4), "big")
                        request_id = int.from_bytes(client_socket.recv(1), "big")
                        print(f"Received request ID: {request_id}")

                        if request_id != 6:
                            print("Download completed. Closing connection.")
                            break
                        
                        # Nhận dữ liệu yêu cầu
                        request_data = client_socket.recv(request_length - 1)  # Trừ đi 1 byte đã nhận cho request_id
                        
                        # Phân tích dữ liệu yêu cầu
                        piece_index = int.from_bytes(request_data[:4], "big")
                        offset = int.from_bytes(request_data[4:8], "big")
                        block_length = int.from_bytes(request_data[8:], "big")
                        
                        # Xử lý yêu cầu và lấy dữ liệu cần gửi lại cho peer
                        response_data = self.process_request(piece_index, offset, block_length, found_files[0])
                        
                        # Gửi dữ liệu phản hồi cho peer
                        response_length = len(response_data) + 9  # 9 bytes cho piece_index, offset và response_id
                        response_payload = (
                            response_length.to_bytes(4, "big")  # Chiều dài của tin nhắn phản hồi
                            + (7).to_bytes(1, "big")  # ID của tin nhắn phản hồi (7 cho "piece")
                            + piece_index.to_bytes(4, "big")  # Chỉ số của mảnh
                            + offset.to_bytes(4, "big")  # Độ lệch bắt đầu của khối trong mảnh
                            + response_data  # Dữ liệu khối được yêu cầu
                        )
                        client_socket.sendall(response_payload) # Gửi dữ liệu phản hồi cho peer
                else:
                    # Gửi phản hồi NOT FOUND nếu peer không có file
                    client_socket.sendall(b"NOT FOUND")
            else:
                print("Không thể trích xuất info hash từ dữ liệu handshake.")
        except Exception as e:
            print("Error handling peer request:", e)
    
    
    def parse_peer_message(self, peer_message):
        message_length = int.from_bytes(peer_message[:4], "big")
        message_id = int.from_bytes(peer_message[4:5], "big")
        return message_length, message_id

    def read_strings_from_file(self):
        file_name = f"info_{self.port}.txt"
        file_dir = "peer_directory"
        file_path = os.path.join(file_dir, file_name)   
        strings = []

        # Đọc các chuỗi từ file
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    strings.append(line.strip())
        except FileNotFoundError:
            pass  # Bỏ qua lỗi nếu file không tồn tại

        return strings

    def find_file_by_infohash(self, infohash, url):
        found_files = []
        file_paths = self.read_strings_from_file()
        # Duyệt qua tất cả các tệp tin và thư mục trong đường dẫn file_paths
        for file_path in file_paths:
            try:
                # Kiểm tra quyền truy cập của tệp tin hoặc thư mục
                os.access(file_path, os.R_OK)
                # Tính thông tin hash của tệp tin
                calculated_infohash = transform.get_info_hash(file_path, url)
                print(f"Calculated info hash: {calculated_infohash}")
                print(f"Received info hash: {infohash}")
                # So sánh thông tin hash của tệp tin với thông tin hash được cung cấp
                if calculated_infohash == infohash:
                    found_files.append(file_path)
            except PermissionError:
                # Bỏ qua các tệp tin hoặc thư mục mà không có quyền truy cập
                pass
            except FileNotFoundError:
                # Bỏ qua các lỗi "No such file or directory"
                pass

        return found_files

    def create_unchoke_message(self):
        # Định dạng của tin nhắn "unchoke": <length prefix><message ID>
        # - Độ dài của tin nhắn là 1 byte (vì không có dữ liệu cụ thể được gửi kèm theo)
        # - Message ID của tin nhắn unchoke là 1
        message_length = (1).to_bytes(4, "big")
        message_id = (1).to_bytes(1, "big")
        unchoke_payload = message_length + message_id
        return unchoke_payload

    def process_request(self, piece_index, offset, block_length, file_path, piece_length=2**20):
        # Open the file for reading in binary mode
        with open(file_path, "rb") as file:
            # Calculate the start position in the file for the requested piece and offset
            piece_start_position = piece_index * piece_length + offset
            # Move to the start position in the file
            file.seek(piece_start_position)
            # Read the block of data from the file
            print(f"Reading piece {piece_index}, offset {offset}, block length {block_length}")
            data = file.read(block_length)
        return data

    def merge_temp_files(self, destination, total_pieces):
        try:
            with open(destination, "wb") as f_dest:
                for piece_index in range(total_pieces):
                    piece_filename = f"{destination}_piece_{piece_index}"
                    if os.path.exists(piece_filename):
                        with open(piece_filename, "rb") as f_piece:
                            f_dest.write(f_piece.read())
                        os.remove(piece_filename)  # Xóa tệp tạm thời sau khi ghép vào tệp hoàn chỉnh
                    else:
                        print(f"Temporary file {piece_filename} not found")
            print(f"Merged temporary files into {destination}")
        except Exception as e:
            print(f"Error merging temporary files: {e}")


def get_local_ip():
    # Sử dụng lệnh `ipconfig` trên Windows
    stream = os.popen('ipconfig')
    output = stream.read()

    # Tìm kiếm địa chỉ IPv4 trong kết quả
    for line in output.split('\n'):
        if "IPv4" in line:
            ip = line.split(":")[1].strip()
            return ip
    return None


if __name__ == "__main__":
    peer = Peer()
    try:
        # Tìm 1 cổng còn trống và gán cho port của peer
        peer.port = peer.find_empty_port()
        print(f"Peer is listening on {get_local_ip()}:{peer.port}")

        # Tạo 1 socket lắng nghe kết nối từ các peer khác
        peer.listen_socket = socket.socket(
            socket.AF_INET, 
            socket.SOCK_STREAM
        ) 
        peer.listen_socket.bind((get_local_ip(), peer.port)) 
        peer.listen_socket.listen(5)

        # Hàm xử lý input người dùng
        def handle_user_input():
            while True:
                command = input("\nEnter command: ")
                command_parts = command.split()

                if command.lower() == "stop":
                    
                    print("Number of bytes download: ", peer.bytes)
                    # Đóng socket của peer khi kết thúc chương trình
                    peer.listen_socket.close()
                    break
                
                elif command.startswith("create"):
                    
                    if len(command_parts) >= 4:
                        file_path = command_parts[1] # Đường dẫn file muốn tạo torrent
                        file_dir = command_parts[2] # Đường dẫn thư mục chứa file torrent 
                        url = command_parts[3] # Địa chỉ HTTP của tracker
                        file_name = os.path.basename(file_path) # Lấy tên file

                        # Tạo file torrent
                        peer.create_torrent_file(file_path, file_dir, url)

                        print(f"Torrent file is created for {file_name}")

                    else:
                        print(f"Torrent file can not be created for {file_name}")

                elif command.startswith("upload"):
                    
                    if len(command_parts) >= 3:
                        torrent_file_path = command_parts[1] # Đường dẫn file torrent
                        tracker_url = command_parts[2] # Địa chỉ HTTP của tracker

                        if os.path.isfile(torrent_file_path):

                            # Thực hiên upload file torrent
                            peer.upload_torrent_file(torrent_file_path, tracker_url)

                        else:
                            print("Error: Torrent file not found.")

                    else:
                        print("Invalid command: Missing file name.")

                elif command.startswith("download"):
                    if len(command_parts) >= 3:
                        threads = []
                        download_dir = command_parts[1] # Đường dẫn thư mục lưu file tải về
                        torrent_file_paths = command_parts[2:].split(" ")
                        print(download_dir)
                        print(torrent_file_paths)


                        for torrent_file_path in torrent_file_paths:
                            if os.path.isfile(torrent_file_path):
                                # Tạo 1 luồng tải về 1 file torrent
                                thread = threading.Thread(
                                    target=peer.download_torrent_file, 
                                    args=(
                                        torrent_file_path, download_dir
                                    )
                                )
                                threads.append(thread)
                                thread.start()
                            else:
                                print("Error: Torrent file not found.")

                        # # Chờ cho các luồng tải các piece
                        # for thread in threads:
                        #     thread.join()

                        # # Gửi yêu cầu tải file từ tracker
                        # if os.path.isfile(torrent_file_path):
                        #     # Thực hiện tải file
                        #     peer.download_torrent_file(torrent_file_path, download_dir)
                        # else:
                        #     print("Error: Torrent file not found.")
           
        # Tạo 1 luồng xử lý input người dùng
        user_input_thread = threading.Thread(target=handle_user_input)
        user_input_thread.start()

        # Luôn lắng nghe kết nối từ các peer khác
        # và tạo 1 luồng xử lý mỗi kết nối
        while True:
            client_peer_socket, client_peer_address = peer.listen_socket.accept()
            print(f"Accepted connection from {client_peer_address}")
            threading.Thread(
                target=peer.handle_peer_request, 
                args=(client_peer_socket, client_peer_address)
            ).start()

    except Exception as e:
        print(f"Error occurred: {e}")