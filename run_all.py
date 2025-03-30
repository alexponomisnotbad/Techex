import subprocess
import time
import sys
import os

# Пути к файлам приложений (предполагается, что они в той же директории)
M1_SCRIPT = "m_one.py"
M2_SCRIPT = "m_two.py"
M3_SCRIPT = "m_three.py"

def run_app(script_name):
    """Запуск приложения в отдельном процессе."""
    if not os.path.exists(script_name):
        print(f"Ошибка: файл {script_name} не найден.")
        sys.exit(1)
    
    try:
        # Запускаем скрипт с помощью python
        process = subprocess.Popen([sys.executable, script_name])
        print(f"Запущено приложение: {script_name} (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"Ошибка при запуске {script_name}: {e}")
        sys.exit(1)

def main():
    print("Запуск приложений M1, M2 и M3...")

    # Запуск M1 (сервер)
    m1_process = run_app(M1_SCRIPT)
    time.sleep(2)  # Задержка 2 секунды, чтобы сервер успел запуститься

    # Запуск M2 (посредник)
    m2_process = run_app(M2_SCRIPT)
    time.sleep(2)  # Задержка 2 секунды, чтобы M2 подключился к M1

    # Запуск M3 (устройство)
    m3_process = run_app(M3_SCRIPT)

    # Ожидание завершения процессов (можно прервать с Ctrl+C)
    try:
        while True:
            # Проверяем, работают ли процессы
            if m1_process.poll() is not None:
                print("M1 завершил работу.")
                break
            if m2_process.poll() is not None:
                print("M2 завершил работу.")
                break
            if m3_process.poll() is not None:
                print("M3 завершил работу.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка всех приложений...")
        m1_process.terminate()
        m2_process.terminate()
        m3_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()