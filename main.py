import sys
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSlider, QListWidget, QFileDialog
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDrag

import pygame
import tempfile
import os

SIZE = 32000
class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)

    def startDrag(self, supportedActions):
        drag = QDrag(self)
        mimeData = self.mimeData(self.selectedItems())
        drag.setMimeData(mimeData)
        drag.exec_(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.handleDropEvent()
        super().dropEvent(event)
        self.parent().send_songs_order()

    def handleDropEvent(self):
        pass


class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.init_socket()
        self.init_ui()
        self.start_byte = 8
        self.start_sec = 0
        self.songs_list = []

        self.streaming = False
        self.buffer = QByteArray()
        self.is_playing = False

        pygame.init()
        pygame.display.init()  # Dodanie inicjalizacji systemu wideo
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(pygame.USEREVENT)

    def init_ui(self):
        self.setWindowTitle('Internet Radio')

        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.toggle_play_streamed_music)
        self.play_button.resize(100, 100)
        self.play_button.move(50, 50)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.upload_button = QPushButton('Upload File')
        self.upload_button.clicked.connect(self.select_and_send_file)

        layout = QVBoxLayout()
        layout.addWidget(self.play_button)
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.upload_button)
        self.listWidget = DraggableListWidget()
        layout.addWidget(self.listWidget)

        self.get_songs_list()

        self.setLayout(layout)
        self.resize(300, 500)

        self.streaming = False
        self.buffer = QByteArray()

    def init_socket(self):
        self.tcp_socket = QTcpSocket(self)
        self.tcp_socket.connected.connect(self.on_connected)
        self.tcp_socket.readyRead.connect(self.on_ready_read)
        self.tcp_socket.errorOccurred.connect(self.on_error)

        server_address = "127.0.0.1"
        server_port = 8080

        self.tcp_socket.connectToHost(server_address, server_port)

    def select_and_send_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Wybierz plik")
        if file_name:
            self.send_file(file_name)

    def send_file(self, file_name):
        try:
            with open(file_name, 'rb') as file:
                data = file.read()
                self.tcp_socket.write(b"BeginFileUpload:" + os.path.basename(file_name).encode())
                self.tcp_socket.write(data)
            self.tcp_socket.write(b"EndFileUpload")
        except Exception as e:
            print(f"Error sending file: {e}")

    def get_songs_list(self):
        self.tcp_socket.write(b"SongsList")

    def send_songs_order(self):
        songs_order = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            songs_order.append(item.text())
        order_str = "UpdateOrder:" + ",".join(songs_order)
        self.tcp_socket.write(order_str.encode())

    def toggle_play_streamed_music(self):
        self.play_button.setEnabled(False)
        if not self.streaming:
            self.tcp_socket.write(b"request_stream")
        else:
            self.tcp_socket.disconnectFromHost()

    def on_connected(self):
        print("Połączono z serwerem")

    def on_ready_read(self):
        try:
            self.buffer += self.tcp_socket.readAll()
            print(f"Received new batch of data. Current buffer size: {len(self.buffer)} bytes")
            list_header_index = self.buffer.indexOf(b"LIST:\n")

            if list_header_index != -1:
                self.buffer = self.buffer[list_header_index + len(b"LIST:\n"):]
                print("in if")
                self.listWidget.clear()
                # Przetwarzanie danych z listy
                while self.buffer.contains(b'\n'):
                    line_end_index = self.buffer.indexOf(b'\n')
                    line = self.buffer[:line_end_index].data()  # Konwersja na bytes
                    print(f"Otrzymano od serwera: {line.decode()}")
                    self.listWidget.addItem(line.decode())

                    # Usunięcie przetworzonej linii z bufora
                    self.buffer = self.buffer[line_end_index + 1:]

            elif len(self.buffer) > 0 and not self.streaming:
                print("Rozpoczęto odtwarzanie strumienia")
                self.streaming = True
                self.play_next_chunk()
        except Exception as e:
            print(f"Błąd przy odbieraniu danych: {e}")

    def on_error(self, socket_error):
        print(f"Błąd gniazda: {socket_error}")

    def play_next_chunk(self):
        # Ustal próg minimalny bufora, aby rozpocząć odtwarzanie
        MIN_BUFFER_THRESHOLD = 16000

        while len(self.buffer) >= MIN_BUFFER_THRESHOLD:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmpfile:
                tmpfile.write(self.buffer[:MIN_BUFFER_THRESHOLD])
                tmpfile_name = tmpfile.name

            self.buffer = self.buffer[MIN_BUFFER_THRESHOLD:]
            pygame.mixer.music.load(tmpfile_name)
            pygame.mixer.music.play()

            # Usuwanie tymczasowego pliku po zakończeniu odtwarzania
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            os.remove(tmpfile_name)
            self.streaming = False
        # Jeśli w buforze jest mniej niż próg, ale wciąż jest coś do odtwarzania
        if len(self.buffer) > 0 and not pygame.mixer.music.get_busy():
            self.streaming = False

    def process_pygame_events(self):
        for event in pygame.event.get():
            if event.type == pygame.USEREVENT:
                self.play_next_chunk()

    def set_volume(self, volume):
        pygame.mixer.music.set_volume(volume / 100)


if __name__ == '__main__':
    app = QApplication([])
    player = MusicPlayer()
    player.show()

    timer = QTimer()
    timer.timeout.connect(player.process_pygame_events)
    timer.start(1)

    sys.exit(app.exec_())
