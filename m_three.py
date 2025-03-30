import sys
import serial
import threading
import time
import struct
from PyQt5 import QtWidgets, uic

class M3App(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("m3.ui", self)
        self.setWindowTitle("M3")
        self.packIdLabel.setText("Pack_id: 0")

        self.com_port = "COM52"  # Укажите ваш COM-порт
        self.baudrate = 9600     # Скорость передачи
        self.message_timeout = 10  # Тайм-аут для получения любых сообщений (в секундах)
        self.response_timeout = 5  # Тайм-аут для ожидания ответа на запрос (в секундах)

        self.serial_port = None
        self.running = True
        self.package_number = 0   # Номер текущего пакета
        self.last_request_time = 0  # Время отправки последнего запроса
        self.waiting_for_response = False  # Флаг ожидания ответа
        self.last_message_time = time.time()  # Время последнего полученного сообщения
        self.buffer = bytearray()

        # Запуск потоков
        threading.Thread(target=self.handle_com_port, daemon=True).start()
        threading.Thread(target=self.check_response_timeout, daemon=True).start()
        threading.Thread(target=self.check_message_timeout, daemon=True).start()

    def handle_com_port(self):
        while self.running:
            if not self.serial_port:
                try:
                    self.serial_port = serial.Serial(self.com_port, self.baudrate, timeout=1)
                    print(f"COM-порт {self.com_port} открыт")
                    self.send_request()  # Отправляем первый запрос при старте
                except Exception as e:
                    print(f"Ошибка открытия COM-порта: {e}")
                    time.sleep(5)
                    continue
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        print(f"Получены данные: {data.hex()}")
                        self.last_message_time = time.time()  # Обновляем время последнего сообщения
                        self.process_response(data)
            except Exception as e:
                print(f"Ошибка чтения COM-порта: {e}")
                if self.serial_port:
                    self.serial_port.close()
                self.serial_port = None
                time.sleep(5)

    def send_request(self):
        if self.serial_port and self.running:
            request = struct.pack('>B B H H', 6, 0x01, self.package_number, 0x0000)
            self.serial_port.write(request)
            self.last_request_time = time.time()  # Запоминаем время отправки
            self.waiting_for_response = True     # Устанавливаем флаг ожидания
            print(f"Отправлен запрос: {request.hex()}")
            self.packIdLabel.setText(f"Pack_id: {self.package_number}")

    def process_response(self, data):
        self.buffer.extend(data)
        while len(self.buffer) >= 1:
            n = self.buffer[0]  # Длина сообщения
            if len(self.buffer) < n:
                break
            message = self.buffer[:n]
            self.buffer = self.buffer[n:]
            if len(message) < 2:
                continue
            msg_type = message[1]
            if msg_type == 0x11 and n >= 6:  # Ответ от M1 через M2
                package_number = (message[2] << 8) | message[3]
                if package_number == self.package_number:
                    self.waiting_for_response = False  # Сбрасываем флаг
                    self.package_number += 1          # Увеличиваем номер пакета
                    self.send_request()               # Отправляем следующий запрос

    def check_response_timeout(self):
        while self.running:
            if self.waiting_for_response:
                time_since_request = time.time() - self.last_request_time
                if time_since_request > self.response_timeout:
                    print(f"Тайм-аут ответа, повторная отправка запроса {self.package_number}")
                    self.send_request()  # Повторно отправляем запрос
            time.sleep(1)

    def check_message_timeout(self):
        while self.running:
            time_since_last_message = time.time() - self.last_message_time
            if time_since_last_message > self.message_timeout:
                print(f"Не получено сообщений в течение {self.message_timeout} секунд, завершение работы")
                self.shutdown()
                break
            time.sleep(1)

    def shutdown(self):
        self.running = False
        if self.serial_port:
            self.serial_port.close()
        QtWidgets.QApplication.quit()

    def closeEvent(self, event):
        self.shutdown()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = M3App()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()