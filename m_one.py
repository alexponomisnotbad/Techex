import sys
import socket
import threading
import time
import configparser
import struct
from PyQt5 import QtWidgets, uic

class M1ServerApp(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        uic.loadUi("m1.ui", self)
        
        self.setWindowTitle("M1")
        self.respondCheckBox.setChecked(True)  # По умолчанию включено
        self.packIdLabel.setText("Pack_id: 0")
        
        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")
        
        self.ip = self.config.get("Server", "ip", fallback="localhost")
        self.port = self.config.getint("Server", "port", fallback=12345)
        self.timeout = self.config.getint("Server", "timeout", fallback=30)

        self.server_socket = None
        self.running = False
        self.last_response_time = time.time()
        
        self.start_server()
        threading.Thread(target=self.check_timeout, daemon=True).start()

    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.ip, self.port))
            self.server_socket.listen(1)
            self.running = True
            threading.Thread(target=self.accept_connections, daemon=True).start()
            print(f"M1: Сервер запущен на {self.ip}:{self.port}")
        except Exception as e:
            print(f"M1: Ошибка запуска сервера: {e}")
            self.running = False

    def accept_connections(self):
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"M1: Подключен клиент {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                print(f"M1: Ошибка принятия подключения: {e}")
                break

    def handle_client(self, client_socket):
        buffer = bytearray()
        while self.running:  # Цикл зависит только от self.running
            try:
                data = client_socket.recv(1024)
                if not data:
                    print("M1: Клиент отключился")
                    break
                self.last_response_time = time.time()
                print(f"M1: Получены данные: {data.hex()}")
                buffer.extend(data)
                
                while len(buffer) >= 1:
                    if len(buffer) < buffer[0]:
                        print(f"M1: Ожидание полного сообщения, буфер: {buffer.hex()}")
                        break
                    n = buffer[0]
                    message = buffer[:n]
                    buffer = buffer[n:]
                    self.process_message(message, client_socket)
            except Exception as e:
                print(f"M1: Ошибка обработки клиента: {e}")
                break
        client_socket.close()
        print("M1: Закрыто соединение с клиентом")

    def process_message(self, message, client_socket):
        if len(message) < 4:
            print(f"M1: Некорректное сообщение: {message.hex()}")
            return
        msg_type = message[1]
        package_number = (message[2] << 8) | message[3]
        packet_data = message[4:]
        print(f"M1: Обработано сообщение: тип={hex(msg_type)}, номер={package_number}, данные={packet_data.hex()}")

        if msg_type == 0x01:
            if len(packet_data) == 2 and packet_data == b'\x00\x00':
                self.packIdLabel.setText(f"Pack_id: {package_number}")
                if self.respondCheckBox.isChecked():  # Отправка ответа только при включенной галочке
                    response_message = struct.pack('>B B H', len(message), 0x11, package_number) + packet_data
                    try:
                        client_socket.send(response_message)
                        print(f"M1: Отправлен ответ: {response_message.hex()}")
                    except Exception as e:
                        print(f"M1: Ошибка отправки ответа: {e}")
                else:
                    print("M1: Ответ не отправлен (галочка снята)")
            elif len(packet_data) == 2 and packet_data == b'\xFF\xFF':
                print("M1: Получен запрос на завершение")
                self.shutdown()

    def check_timeout(self):
        while self.running:
            # Убрано автоматическое завершение по тайм-ауту, оставлено только логирование
            current_time = time.time()
            if current_time - self.last_response_time >= self.timeout:
                print(f"M1: Прошло {self.timeout} сек с последнего сообщения")
            time.sleep(1)

    def shutdown(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        QtWidgets.QApplication.quit()

    def closeEvent(self, event):
        self.shutdown()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = M1ServerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()