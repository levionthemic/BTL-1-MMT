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
        os.makedirs(file_dir, exist_ok=True)  # Tạo thư mục nếu chưa tồn tại
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
        file_name = os.path.basename(file_path)
        self.write_string_to_file(file_path)
        print(f"Creating torrent file for {file_name}...")
        info_hash = transform.create_torrent(file_path, tracker_url, os.path.join(file_dir, f'{file_name}.torrent'))

    def upload_torrent_file(self, file_path, tracker_url):
        try:
            # Đọc dữ liệu từ file torrent
            with open(file_path, 'rb') as torrent_file:
                torrent_data = torrent_file.read()
            
            info_hash = str(hashlib.sha1(torrent_data).hexdigest())
            try:
                tracker_url = tracker_url + f':6880' + "/announce/upload" + "?info_hash=" + info_hash
                # params = {"port": self.port}  # Thêm thông tin cổng vào yêu cầu
                response = requests.get(tracker_url)
                if response.status_code == 200:
                    print("Upload to tracker successfully.")
                else:
                    print("Failed to upload to tracker. Status code:", response.status_code)
            except Exception as e:
                print("Error connecting to tracker:", e)
        except Exception as e:
            print(f"Error uploading torrent file: {e}")

    def download_torrent_file(self, torrent_file_path, destination):
        torrent_file_name = os.path.basename(torrent_file_path)
        # Tách phần tên tệp ra khỏi phần mở rộng (ví dụ: 't.png.torrent' sẽ trở thành 't.png')
        file_name_without_extension = os.path.splitext(torrent_file_name)[0]
        # Kết hợp đường dẫn của thư mục đích với tên tệp (ví dụ: '/home/linh/Documents/codecrafters-bittorrent-python/app/res/t.png')
        file_path = os.path.join(destination, file_name_without_extension)
        destination = file_path
        try:
            with open(torrent_file_path, 'rb') as torrent_file:
                torrent_data = torrent_file.read()
            
            decoded_torrent = bencodepy.decode(torrent_data)
            decoded_str_keys = {transform.bytes_to_str(k): v for k, v in decoded_torrent.items()}

            info_hash = str(hashlib.sha1(torrent_data).hexdigest())
            announce_url = decoded_torrent[b"announce"].decode()
                
            try:
                announce_url_down = announce_url + ":6880/announce" + "/download"
                response = requests.get(announce_url_down, params={"info_hash": info_hash})
             
                # Kiểm tra mã trạng thái của phản hồi
                if response.status_code == 200:
                    ip_port_pairs = response.text.split(",")
                    # Duyệt qua từng cặp ip và port
                    formatted_ip_addresses = []
                    for pair in ip_port_pairs:
                        ip, port = pair.strip().split(":")
                        if port != self.port:
                            formatted_ip_addresses.append((ip, int(self.port)))
                    print("Formatted IP addresses:", formatted_ip_addresses)

                    threads = []
                    total_pieces = math.ceil(decoded_str_keys["info"][b"length"] / decoded_str_keys["info"][b"piece length"])
                    print(f"Total pieces: {total_pieces}")
                    pieces_per_thread = total_pieces // len(formatted_ip_addresses) + 1
                    print(f"Pieces per thread: {pieces_per_thread}")
                    start_piece = 0
                    for ip_address in formatted_ip_addresses:
                        end_piece = start_piece + pieces_per_thread
                        if end_piece > total_pieces:
                            end_piece = total_pieces
                        thread = threading.Thread(target=self.download_range, args=(ip_address, torrent_data, destination, start_piece, end_piece, announce_url, total_pieces))
                        threads.append(thread)
                        start_piece = end_piece
                        thread.start()
                    # Wait for all threads to finish
                    for thread in threads:
                        thread.join()
                else:
                    print("Error:", response.status_code)
            except Exception as e:
                print(f"Error connecting to tracker: {e}")
        except Exception as e:
            print(f"Error downloading torrent file: {e}")

    def download_range(self, ip_address, file_data, destination, start_piece, end_piece, announce_url, total_pieces):
        for piece in range(start_piece, end_piece):
            self.download_piece(ip_address, file_data, destination, str(piece), announce_url, total_pieces)

    def download_piece(self, ip_address, file_data, destination, piece, announce_url, total_pieces):
        peer_ip, peer_port = ip_address
        sock = socket.create_connection((peer_ip, peer_port))
        
        sha1 = str(hashlib.sha1(file_data).hexdigest())
        payload = sha1 + " " + announce_url
        sock.sendall(payload.encode('utf-8'))
        
        response = sock.recv(1024).decode('utf-8')
        if response == "OK":
            # send interested message
            interested_payload = (2).to_bytes(4, "big") + (2).to_bytes(1, "big")
            sock.send(interested_payload)
            # received unchoke message
            unchoke_msg = sock.recv(5)
            print(f"Received unchoke message from {ip_address}: {unchoke_msg}")
            message_length, message_id = self.parse_peer_message(unchoke_msg)
            if message_id != 1:
                raise SystemError("Expecting unchoke id of 1")

            decoded_torrent = bencodepy.decode(file_data)
            decoded_str_keys = {transform.bytes_to_str(k): v for k, v in decoded_torrent.items()}
            
            # break the pieces up and send request for each
            bit_size = 16 * 1024
            final_block = b""
            piece_length = decoded_str_keys["info"][b"piece length"]
            total_length = decoded_str_keys["info"][b"length"]
            # if final piece, offset piece length
            if int(piece) == math.ceil(total_length / piece_length) - 1:
                # then the piece length is the remainder
                piece_length = total_length % piece_length
            
            # Tạo tên tệp tạm thời dựa trên index của piece
            piece_filename = f"{destination}_piece_{piece}"
            
            for offset in range(0, piece_length, bit_size):
                # block length
                block_length = min(bit_size, piece_length - offset)
                request_data = (
                    int(piece).to_bytes(4, "big")
                    + offset.to_bytes(4, "big")
                    + block_length.to_bytes(4, "big")
                )
                request_payload = (
                    (len(request_data) + 1).to_bytes(4, "big")
                    + (6).to_bytes(1, "big")
                    + request_data
                )
                sock.send(request_payload)

                message_length = int.from_bytes(sock.recv(4), "big")
                message_id = int.from_bytes(sock.recv(1), "big")
                if message_id != 7:
                    raise SystemError("Expecting piece id of 7")
                piece_index = int.from_bytes(sock.recv(4), "big")
                begin = int.from_bytes(sock.recv(4), "big")
                received = 0
                full_block = b""
                size_of_block = message_length - 9
                while received < size_of_block:
                    block = sock.recv(size_of_block - received)
                    full_block += block
                    received += len(block)
                final_block += full_block
                print(f"Downloading piece {piece}, offset {offset}, block length {block_length} from {ip_address}")
        
        try:
            # Lưu dữ liệu của piece vào tệp tạm thời
            with open(piece_filename, "wb") as f:
                f.write(final_block)
        except Exception as e:
            print(e)

        # Kiểm tra xem tất cả các phần đã được tải xong chưa
        downloaded_pieces = [f"{destination}_piece_{piece}" for piece in range(total_pieces)]
        d = len(list(piece_file for piece_file in downloaded_pieces if os.path.exists(piece_file)))

        print(f"Downloaded {d} pieces out of {len(downloaded_pieces)}")
        if all(os.path.exists(piece_file) for piece_file in downloaded_pieces):
            self.merge_temp_files(destination, math.ceil(total_length / piece_length))
            self.bytes += total_length  # Cập nhật số byte đã tải
            print("Download completed.")

    def parse_peer_message(self, peer_message):
        message_length = int.from_bytes(peer_message[:4], "big")
        message_id = int.from_bytes(peer_message[4:5], "big")
        return message_length, message_id

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
        # Duyệt qua tất cả các tệp tin và thư mục trong đường dẫn start_path
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

    # def merge_temp_files(self, destination, total_pieces):
    #     try:
    #         with open(destination, "wb") as f_dest:
    #             for piece_index in range(total_pieces):
    #                 piece_filename = f"{destination}_piece_{piece_index}"
    #                 if os.path.exists(piece_filename):
    #                     with open(piece_filename, "rb") as f_piece:
    #                         f_dest.write(f_piece.read())
    #                     os.remove(piece_filename)  # Xóa tệp tạm thời sau khi ghép vào tệp hoàn chỉnh
    #                 else:
    #                     print(f"Temporary file {piece_filename} not found")
    #         print(f"Merged temporary files into {destination}")
    #     except Exception as e:
    #         print(f"Error merging temporary files: {e}")

def get_local_ip(interface='Ethernet'):
    # # Chạy lệnh ifconfig và lấy kết quả
    # result = subprocess.run(['ifconfig', interface], capture_output=True, text=True)

    # # Phân tích kết quả để tìm địa chỉ IP
    # ip_pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
    # match = re.search(ip_pattern, result.stdout)

    # # Trả về địa chỉ IP nếu tìm thấy, nếu không trả về None
    # if match:
    #     return match.group(1)
    # else:
    #     return None
    result = subprocess.run(['ipconfig'], capture_output=True, text=True)
    # Tìm dòng chứa thông tin về interface
    interface_line = f'IPv4 Address'
    lines = result.stdout.splitlines()
    for line in lines:
        if interface_line in line:
            return line.split(": ")[1]
    return None

if __name__ == "__main__":
    peer = Peer()
    try:
        peer.port = peer.find_empty_port()
        print(f"Peer is listening on {get_local_ip()}:{peer.port}")

        # Create a new socket for listening to peer connections
        peer.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        
        peer.listen_socket.bind((get_local_ip(), peer.port)) 
        # print ip address of local that other can see 
        
        peer.listen_socket.listen(5)

        # Define a function to handle user input
        def handle_user_input():
            while True:
                command = input("\nEnter command: ")
                command_parts = command.split()

                if command.lower() == "stop":
                    
                    print("Number of bytes download: ", peer.bytes)
                    # Đóng socket nghe khi kết thúc chương trình
                    peer.listen_socket.close()
                    break
                
                elif command.startswith("create"):
                    
                    if len(command_parts) >= 4:
                        file_path = command_parts[1]
                        file_dir = command_parts[2]
                        url = command_parts[3]
                        file_name = os.path.basename(file_path)
                        peer.create_torrent_file(file_path, file_dir, url)
                        print(f"Torrent file is created for {file_name}")
                    else:
                        print(f"Torrent file can not be created for {file_name}")

                elif command.startswith("upload"):
                    
                    if len(command_parts) >= 3:
                        torrent_file_path = command_parts[1]
                        new_url = command_parts[2]
                        if os.path.isfile(torrent_file_path):
                            peer.upload_torrent_file(torrent_file_path, new_url)
                        else:
                            print("Error: Torrent file not found.")
                    else:
                        print("Invalid command: Missing file name.")

                elif command.startswith("download"):
                    
                    if len(command_parts) >= 3:
                        torrent_file_path = command_parts[1]
                        destination = command_parts[2]
                        # Gửi yêu cầu tải file từ tracker
                        if os.path.isfile(torrent_file_path):
                            peer.download_torrent_file(torrent_file_path, destination)
                        else:
                            print("Error: Torrent file not found.")
           
        # Create a thread for handling user input
        user_input_thread = threading.Thread(target=handle_user_input)
        user_input_thread.start()

        while True:
            client_socket, client_address = peer.listen_socket.accept()
            print(f"Accepted connection from {client_address}")
            threading.Thread(target=peer.handle_peer_request, args=(client_socket, client_address)).start()

    except Exception as e:
        print(f"Error occurred: {e}")