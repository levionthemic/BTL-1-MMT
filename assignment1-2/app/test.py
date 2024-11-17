import os

def get_local_ip_os():
    # Sử dụng lệnh `ipconfig` trên Windows
    stream = os.popen('ipconfig')
    output = stream.read()

    # Tìm kiếm địa chỉ IPv4 trong kết quả
    for line in output.split('\n'):
        if "IPv4" in line:
            ip = line.split(":")[1].strip()
            return ip
    return None

local_ip = get_local_ip_os()
print("Local IP Address:", local_ip)
