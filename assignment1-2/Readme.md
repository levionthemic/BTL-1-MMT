# Hướng dẫn sử dụng chương trình

Đây là hướng dẫn cơ bản về cách sử dụng chương trình của chúng tôi để tạo, tải lên và tải xuống file torrent.

## Cài đặt môi trường ảo Python

Đầu tiên, bạn cần tạo một môi trường ảo Python để cài đặt và quản lý các gói phụ thuộc của chương trình. Bạn có thể làm điều này bằng lệnh sau:

```
python3 -m venv myenv
```

Sau đó, bạn cần kích hoạt môi trường ảo bằng lệnh:

```
source myenv/bin/activate
```

## Chạy chương trình

1. Di chuyển đến thư mục chứa mã nguồn của chương trình:

```
cd app
```

2. Chạy tracker bằng lệnh:

```
python3 tracker.py
```

3. Chạy peer bằng lệnh:

```
python3 peer.py
```

## Các chức năng chính

### Tạo file torrent:

Để tạo file torrent, bạn cần sử dụng lệnh sau:

```
create <đường dẫn đến file muốn tạo torrent> <đường dẫn đến thư mục lưu file torrent> <địa chỉ http của tracker>
```

### Upload file torrent:

Để upload file torrent, bạn cần sử dụng lệnh sau:

```
upload <đường dẫn đến file torrent> <địa chỉ http của tracker>
```

### Download file torrent:

Để download file torrent, bạn cần sử dụng lệnh sau:

```
download <đường dẫn đến file torrent> <đường dẫn đến thư mục lưu file tải về>
```

Vui lòng thay thế các thông tin cụ thể như đường dẫn và địa chỉ http theo yêu cầu của bạn.

Chúc bạn sử dụng chương trình thành công!