import socket
import threading
import json
import os
import transform
import sys
import hashlib
import os
import bencodepy
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.parse
import subprocess
from urllib.request import urlopen
import re as r



class MyTrackerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Lấy đường dẫn từ yêu cầu GET
        print("Accept GET")
        path = urlparse(self.path).path
        ip = get_local_ip()

        # Kiểm tra xem yêu cầu có phải là "/announce" hay không
        if path.startswith("/announce/upload"):

            # Trích xuất tham số từ query
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Lấy giá trị của tham số 'info_hash'
            info_hash = query_params.get('info_hash', [None])[0]

            # Kiểm tra xem info hash có tồn tại không
            self._update_seeder(query_params.get('port', [None])[0], info_hash, ip)

            # Trả về mã trạng thái 200 và thông báo "OK"
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"OK")

        elif path.startswith("/announce/download"):
            # Trích xuất tham số từ query
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Lấy giá trị của tham số 'info_hash'
            info_hash = query_params.get('info_hash', [None])[0]

            # Kiểm tra xem info hash có tồn tại không
            response = self.find_and_print_line("tracker_directory/seeder_info.txt", info_hash)

            if response:
                # Trả về mã trạng thái 200 
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                # Gửi nội dung dòng đã tìm thấy
                self.wfile.write(response.encode()) 

            else:
                # Trả về mã trạng thái 404 nếu không tìm thấy dòng
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Not Found")

        else:
            # Nếu đường dẫn không hợp lệ, trả về mã trạng thái 404
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Not Found")

    def _update_seeder(self, port, info_hash, ip):
        try:
            seeder_info = f"{ip}:{port}"
            file_dir = "tracker_directory"
            file_name = "seeder_info.txt"
            file_path = os.path.join(file_dir, file_name)

            # Tạo thư mục nếu chưa tồn tại
            os.makedirs(file_dir, exist_ok=True)  

            # Chuỗi chứa thông tin của seeder
            seeder_line = f"{info_hash}: {seeder_info}\n"

            # Kiểm tra xem file đã tồn tại hay chưa
            if os.path.isfile(file_path): 
                # Đọc nội dung hiện tại của file
                with open(file_path, 'r') as file:
                    lines = file.readlines()
            else:
                lines = []

            # Kiểm tra xem seeder đã tồn tại trong file hay chưa
            seeder_exists = False
            for i, line in enumerate(lines):
                if info_hash in line:
                    # Seeder đã tồn tại, kiểm tra xem port đã tồn tại trong hàng hay chưa
                    seeder_ports = line.split(':')[1].strip().split(',')
                    if port in seeder_ports:
                        # Port đã tồn tại, không cần cập nhật
                        print(f"Port {port} already exists for {info_hash}. Skipping update.")
                        return
                    else:
                        # Port chưa tồn tại, cập nhật thông tin
                        seeder_exists = True
                        if line[-1] != '\n':
                            line += '\n'  # Đảm bảo dòng cuối cùng có ký tự xuống dòng
                        lines[i] = line.rstrip() + f", {seeder_info}\n"  # Thêm thông tin mới vào dòng hiện tại
                        break

            # Nếu seeder chưa tồn tại, thêm một dòng mới
            if not seeder_exists:
                lines.append(seeder_line)

            # Ghi lại toàn bộ nội dung vào file
            with open(file_path, 'w') as file:
                file.writelines(lines)

            print(f"Seeder information updated for {file_name}.")
            
        except Exception as e:
            print(f"Error updating seeder information: {e}")
    
    def find_and_print_line(self, file_path, target_string):
        with open(file_path, 'r') as file:
            for line in file:
                if target_string + ": " in line:
                    # In ra phần sau của dòng chứa chuỗi
                    return line.split(": ", 1)[1]  
        return None

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
   

def main(port=8080):
    # Khởi tạo một máy chủ HTTP với cổng được chỉ định
    server_address = (get_local_ip(), port)
    httpd = HTTPServer(server_address, MyTrackerHandler)
    print(f"Tracker server is running on {get_local_ip()}:{port}")

    # Bắt đầu lắng nghe yêu cầu
    httpd.serve_forever()
    

# Khởi động máy chủ tracker
main()

