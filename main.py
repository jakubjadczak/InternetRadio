import sys
from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSlider, QListWidget, QFileDialog
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import Qt, QMimeData, QTimer
from PyQt5.QtGui import QDrag
from time import sleep
from io import BytesIO
import pygame
import tempfile
import os

#Zakladamy ze piosenki maja unikatowe nazwy,
#Metoda get_songs_list, wywolywana na poczatku oraz co n-ty fragment granego utworu
#Metoda get_songs_order, jest wywolywana przy kazdej zmianie kolejnosci i zwraca aktualna kolejnosc, musi wyslac do serwera



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
        # self.parent().get_songs_order()
        self.parent().send_songs_order()

    def handleDropEvent(self):
        # Tu umieść kod, który ma się wykonać po upuszczeniu elementu
        print("Element został upuszczony")
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
        self.setWindowTitle('Music Streaming Client')

        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.toggle_play_streamed_music)
        self.play_button.resize(100, 100)
        self.play_button.move(50, 50)

        self.test_button = QPushButton('Test')
        self.test_button.clicked.connect(self.send_test_request)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.upload_button = QPushButton('Upload File')
        self.upload_button.clicked.connect(self.select_and_send_file)


        layout = QVBoxLayout()
        layout.addWidget(self.play_button)
        layout.addWidget(self.test_button)
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.upload_button)
        self.listWidget = DraggableListWidget()
        layout.addWidget(self.listWidget)

        self.get_songs_list()

        self.setLayout(layout)
        self.setWindowTitle('Internet Radio')
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
                print(self.tcp_socket.write(b"BeginFileUpload:" + os.path.basename(file_name).encode()))
                print("a")
                print(self.tcp_socket.write(data))
                print("b")
            print(self.tcp_socket.write(b"EndFileUpload"))
        except Exception as e:
            print(f"Error sending file: {e}")

    def get_songs_list(self):
        self.tcp_socket.write(b"SongsList")
        print("Wyslano zadanie o liste utworow")

    def send_songs_order(self):
        songs_order = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            songs_order.append(item.text())

        print(songs_order)

        order_str = "UpdateOrder:" + ",".join(songs_order)
        self.tcp_socket.write(order_str.encode())
        print("Wysłano aktualną kolejność utworów do serwera")

    def toggle_play_streamed_music(self):
        self.play_button.setEnabled(False)
        print('toggle play')
        if not self.streaming:
            self.tcp_socket.write(b"request_stream")
            print("Wysłano żądanie strumieniowania do serwera")

        else:
            self.tcp_socket.disconnectFromHost()

    def send_test_request(self):
        self.tcp_socket.write(b"test")
        print("Wysłano żądanie test do serwera")

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

                # Przetwarzanie danych z listy
                while self.buffer.contains(b'\n'):
                    line_end_index = self.buffer.indexOf(b'\n')
                    line = self.buffer[:line_end_index].data()  # Konwersja na bytes
                    print(f"Otrzymano od serwera: {line.decode()}")
                    self.listWidget.addItem(line.decode())

                    # Usunięcie przetworzonej linii z bufora
                    self.buffer = self.buffer[line_end_index + 1:]

            elif len(self.buffer) >= 50000 and not self.streaming:
                print("Rozpoczęto odtwarzanie strumienia")
                self.streaming = True
                self.start_continuous_playback()

        except Exception as e:
            print(f"Błąd przy odbieraniu danych: {e}")

    def on_error(self, socket_error):
        print(f"Błąd gniazda: {socket_error}")


    def start_continuous_playback(self):
        if not self.is_playing:
            self.is_playing = True
            self.play_next_chunk()

    def play_next_chunk(self):
        if len(self.buffer) >= 50000:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmpfile:
                tmpfile.write(self.buffer[:50000])
                tmpfile_name = tmpfile.name

            self.buffer = self.buffer[50000:]
            pygame.mixer.music.load(tmpfile_name)
            pygame.mixer.music.play()

            # Usuwanie tymczasowego pliku po zakończeniu odtwarzania
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            os.remove(tmpfile_name)
        else:
            self.is_playing = False

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
    timer.start(0)

    sys.exit(app.exec_())