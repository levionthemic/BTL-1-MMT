import hashlib
import os
import bencodepy


def decode(value):
    return bencodepy.decode(value)

def bytes_to_str(data):
    if isinstance(data, bytes):
        return data.decode()
    raise TypeError(f"Type not serializable: {type(data)}")

def create_torrent(file_path, announce_url, output_file):
    
    # Tính kích thước của 1 piece theo byte
    piece_length = 2**20  # 1 MB

    # Tính dung lượng file
    with open(file_path, 'rb') as file:
        file_size = os.path.getsize(file_path)

        # Tính số piece
        num_pieces = file_size // piece_length
        if file_size % piece_length:
            num_pieces += 1

        # Sinh mã băm (hash) của piece
        pieces = []
        hasher = hashlib.sha1()
        while True:
            piece_data = file.read(piece_length)
            if not piece_data:
                break
            hasher.update(piece_data)
            pieces.append(hasher.digest())

        # Tạo torrent metadata dictionary
        metadata = {
            b'announce': announce_url.encode(),  # Encode announce URL to bytes
            b'info': {
                b'name': os.path.basename(file_path).encode(),  # Encode name to bytes
                b'length': file_size,
                b'piece length': piece_length,
                b'pieces': b''.join(pieces),
                #b'peers': peer_addresses  # Encode peer addresses to bytes
            }
        }

        # Mã hóa metadata sử dụng bencode
        encoded_metadata = bencodepy.encode(metadata)

        # Ghi encoded metadata ra output file
        with open(output_file, 'wb') as torrent_file:
            torrent_file.write(encoded_metadata)

        decoded = decode(encoded_metadata)
        # Convert bytes keys to strings and remove leading 'b'
        decoded_str_keys = {bytes_to_str(k): v for k, v in decoded.items()}

        tracker_url = decoded_str_keys['announce'].decode()
        print(f"Tracker URL: {tracker_url}")

        # Access the nested 'length' key within 'info'
        info = decoded_str_keys['info']
        print(f"Length: {info[b'length']}")

        res = str(hashlib.sha1(encoded_metadata).hexdigest())
        print("Info Hash: " + str(res))

        info_hash = hashlib.sha1(encoded_metadata).hexdigest()
        return info_hash

def get_info_hash(file_path, announce_url):
    piece_length = 2**20  # 1 MB
    
    with open(file_path, 'rb') as file:
        file_size = os.path.getsize(file_path)

        # Calculate the number of pieces
        num_pieces = file_size // piece_length
        if file_size % piece_length:
            num_pieces += 1

        # Generate the pieces hashes
        pieces = []
        hasher = hashlib.sha1()
        while True:
            piece_data = file.read(piece_length)
            if not piece_data:
                break
            hasher.update(piece_data)
            pieces.append(hasher.digest())

        # Construct the torrent metadata dictionary
        metadata = {
            b'announce': announce_url.encode(),  # Encode announce URL to bytes
            b'info': {
                b'name': os.path.basename(file_path).encode(),  # Encode name to bytes
                b'length': file_size,
                b'piece length': piece_length,
                b'pieces': b''.join(pieces),
                #b'peers': peer_addresses  # Encode peer addresses to bytes
            }
        }

        # Encode the metadata using bencode
        encoded_metadata = bencodepy.encode(metadata)
        return str(hashlib.sha1(encoded_metadata).hexdigest())
