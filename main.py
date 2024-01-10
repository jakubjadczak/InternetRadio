import sys
from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSlider, QListWidget
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag
from io import BytesIO
import pygame

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
        self.parent().get_songs_order()

    def handleDropEvent(self):
        # Tu umieść kod, który ma się wykonać po upuszczeniu elementu
        # print("Element został upuszczony")
        pass


class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.init_socket()
        self.init_ui()
        self.start_byte = 8
        self.start_sec = 0
        self.songs_list = []

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


        layout = QVBoxLayout()
        layout.addWidget(self.play_button)
        layout.addWidget(self.test_button)
        layout.addWidget(self.volume_slider)
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
        server_port = 8082

        self.tcp_socket.connectToHost(server_address, server_port)

    def get_songs_order(self):
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            print(item.text())

    def get_songs_list(self):
        self.tcp_socket.write(b"SongsList")
        print("Wyslano zadanie o liste utworow")

    def toggle_play_streamed_music(self):
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
        pygame.init()
        pygame.mixer.init()
        one = self.buffer[:8]
        two = self.buffer[self.start_byte:]
        music_bytes = b''.join(one+two)
        music_stream = BytesIO(music_bytes)
        sound = pygame.mixer.music.load(music_stream)
        self.start_byte += 50000
        self.streaming = False
        pygame.mixer.music.play()


    def set_volume(self):
        volume = self.volume_slider.value()
        print(f"Setting volume to {volume}")

if __name__ == '__main__':
    app = QApplication([])
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
