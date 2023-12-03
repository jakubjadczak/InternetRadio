import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSlider, QMessageBox
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QAudioOutput, QAudioFormat
from PyQt5.QtNetwork import QTcpSocket, QHostAddress
from PyQt5.QtCore import QUrl, QByteArray, pyqtSlot, QBuffer, QIODevice
import pygame
from io import BytesIO


class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()
        self.init_socket()

    def init_ui(self):
        self.setWindowTitle('Music Streaming Client')

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()

        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.toggle_play_streamed_music)

        self.test_button = QPushButton('Test')
        self.test_button.clicked.connect(self.send_test_request)

        self.volume_slider = QSlider()
        self.volume_slider.setOrientation(1)  # Vertical orientation
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)

        layout = QVBoxLayout()
        layout.addWidget(self.play_button)
        layout.addWidget(self.test_button)
        layout.addWidget(self.volume_slider)

        self.setLayout(layout)

        self.streaming = False
        self.buffer = QByteArray()

    def init_socket(self):
        #wywolywane w init()
        self.tcp_socket = QTcpSocket(self)
        self.tcp_socket.connected.connect(self.on_connected)
        self.tcp_socket.readyRead.connect(self.on_ready_read)
        self.tcp_socket.errorOccurred.connect(self.on_error)

        server_address = QHostAddress('127.0.0.1')  # Replace with the server's IP address
        server_port = 8081  # Replace with the server's port

        self.tcp_socket.connectToHost(server_address, server_port)

    def toggle_play_streamed_music(self):
        print('toggle play')
        if not self.streaming:
            self.tcp_socket.write(b"request_stream")
            print("Wysłano żądanie strumieniowania do serwera")
            self.play_buffered_music()

        else:
            self.tcp_socket.disconnectFromHost()

    def send_test_request(self):
        self.tcp_socket.write(b"test")
        print("Wysłano żądanie test do serwera")

    @pyqtSlot()
    def on_connected(self):
        print("Połączono z serwerem")

    def on_ready_read(self):
        print('in on ready read')
        try:
            self.buffer += self.tcp_socket.readAll()
            print(self.buffer)
            print(len(self.buffer))
            if len(self.buffer) > 1024:
                self.play_buffered_music()
            if not self.streaming:
                print("Rozpoczęto odtwarzanie strumienia")
                self.streaming = True
        except Exception as e:
            print(f"Błąd przy odbieraniu danych: {e}")

        # Sprawdź, czy otrzymano odpowiedź na żądanie "test"
        if b"test ok" in self.buffer:
            response_text = str(self.buffer, 'utf-8')  # Konwersja QByteArray na string
            QMessageBox.information(self, 'Odpowiedź na żądanie "test"', response_text)
            self.buffer.clear()

    def on_error(self, socket_error):
        print(f"Błąd gniazda: {socket_error}")

    def play_buffered_music(self):
        print('In buffered music', len(self.buffer))
        
        # if len(self.buffer) >= 1024:
        buffer = QBuffer()
        buffer.setData(self.buffer)
        buffer.open(QIODevice.ReadOnly)


        pygame.init()
        pygame.mixer.init()
        
        sound = pygame.mixer.Sound(BytesIO(self.buffer))
        
        sound.play()

    def set_volume(self):
        volume = self.volume_slider.value()
        self.media_player.setVolume(volume)
        self.audio_output.setVolume(volume)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
