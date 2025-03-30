import sys
import socket
import threading
import time
import serial
import struct
import configparser
from PyQt5 import QtWidgets, uic

class M2ClientApp(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("m2.ui", self)
        self.setWindowTitle("M2")
        self.packIdLabel.setText("Pack_id: 0")
        self.exchangeCheckBox.setChecked(False)

        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")
        self.server_ip = self.config.get("Client", "ip", fallback="localhost")
        self.server_port = self.config.getint("Client", "port", fallback=12345)
        self.reconnect_interval = self.config.getint("Client", "reconnect_interval", fallback=5)
        self.response_timeout = self.config.getint("Client", "response_timeout", fallback=10)
        self.exchange_timeout = self.config.getint("Client", "exchange_timeout", fallback=15)
        self.com_port = self.config.get("COM", "portcom", fallback="COM25")
        self.baudrate = self.config.getint("COM", "baudrate", fallback=9600)
        self.heartbeat_threshold = 3  # Heartbeat отправляется, если нет ответа от M1 2 секунды

        self.client_socket = None
        self.serial_port = None
        self.running = True
        self.last_m1_response_time = time.time()
        self.last_m3_time = time.time()
        self.last_request_time = None
        self.shutdown_sent = False
        self.buffer = bytearray()

        threading.Thread(target=self.connect_to_server, daemon=True).start()
        threading.Thread(target=self.handle_com_port, daemon=True).start()
        threading.Thread(target=self.check_m1_response, daemon=True).start()

    def connect_to_server(self):
        while self.running:
            if not self.is_socket_connected():
                try:
                    self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.client_socket.connect((self.server_ip, self.server_port))
                    threading.Thread(target=self.handle_server, daemon=True).start()
                except Exception as e:
                    print(f"M2: Ошибка подключения к M1: {e}")
                    self.client_socket = None
                    time.sleep(self.reconnect_interval)

    def is_socket_connected(self):
        try:
            self.client_socket.getpeername()
            return True
        except:
            return False

    def handle_server(self):
        while self.running and self.client_socket:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    break
                self.last_m1_response_time = time.time()
                if self.serial_port and not self.shutdown_sent:
                    self.serial_port.write(data)
                    print(f"M2: Передан ответ от M1 в M3: {data.hex()} в {time.strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"M2: Ошибка при получении данных от M1: {e}")
                break
        if self.client_socket:
            self.client_socket.close()
        self.client_socket = None

    def handle_com_port(self):
        while self.running:
            if not self.serial_port:
                try:
                    self.serial_port = serial.Serial(self.com_port, self.baudrate, timeout=1)
                    print(f"M2: COM-порт {self.com_port} открыт")
                except Exception as e:
                    print(f"M2: Ошибка открытия COM-порта: {e}")
                    time.sleep(self.reconnect_interval)
                    continue
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if not data:
                        continue
                    self.buffer.extend(data)
                    while len(self.buffer) >= 1:  # Проверяем, есть ли данные в буфере
                        if self.buffer[0] > len(self.buffer):  # Если длина больше текущего буфера
                            break
                        n = self.buffer[0]
                        if len(self.buffer) >= n:
                            message = self.buffer[:n]
                            self.buffer = self.buffer[n:]
                            msg_type = message[1]
                            package_number = (message[2] << 8) | message[3]
                            packet_data = message[4:n]
                            self.last_m3_time = time.time()
                            if msg_type == 0x01:
                                if len(packet_data) == 2 and packet_data == b'\x00\x00':
                                    self.packIdLabel.setText(f"Pack_id: {package_number}")
                            if self.client_socket and not self.shutdown_sent:
                                self.client_socket.send(message)
                                print(f"M2: Отправлен запрос в M1: {message.hex()}")
                                self.last_request_time = time.time()
                        else:
                            break
            except Exception as e:
                print(f"M2: Ошибка чтения COM-порта: {e}")
                if self.serial_port:
                    self.serial_port.close()
                self.serial_port = None
                time.sleep(self.reconnect_interval)

    def check_m1_response(self):
        while self.running:
            time_since_m1 = time.time() - self.last_m1_response_time
            if time_since_m1 > self.heartbeat_threshold:
                if self.serial_port and not self.shutdown_sent:
                    try:
                        heartbeat_message = struct.pack('>B B H', 4, 0xFE, 0x0000)
                        self.serial_port.write(heartbeat_message)
                        print(f"M2: Отправлен heartbeat в M3: {heartbeat_message.hex()} в {time.strftime('%H:%M:%S')}")
                    except Exception as e:
                        print(f"M2: Ошибка отправки heartbeat: {e}")
            time.sleep(1)

    def send_shutdown_request(self):
        if self.client_socket and not self.shutdown_sent:
            shutdown_message = struct.pack('>B B H B B', 6, 0x01, 0, 0xFF, 0xFF)
            try:
                self.client_socket.send(shutdown_message)
                self.shutdown_sent = True
                if self.serial_port:
                    self.serial_port.close()
                    self.serial_port = None
            except Exception as e:
                print(f"M2: Ошибка отправки shutdown: {e}")

    def closeEvent(self, event):
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        if self.serial_port:
            self.serial_port.close()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = M2ClientApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()