import sys
import socket
import pyaudio
import wave
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

# Tutaj możesz umieścić logikę do odtwarzania strumienia audio przychodzącego przez UDP
# Poniżej znajduje się przykładowy szkielet, który odbiera dane przez UDP

class AudioReceiver:
    def __init__(self):
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 2
        self.RATE = 44100

        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=self.FORMAT,
                                      channels=self.CHANNELS,
                                      rate=self.RATE,
                                      output=True,
                                      frames_per_buffer=self.CHUNK)

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('127.0.0.1', 8080))  # Ustaw adres i port do nasłuchiwania

    def receive_audio(self):
        while True:
            data, addr = self.udp_socket.recvfrom(1024)  # Dostępne dane z adresu addr
            self.stream.write(data)

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        self.udp_socket.close()

class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("UDP Music Player")
        self.setGeometry(300, 200, 300, 100)

        self.play_button = QPushButton('Play', self)
        self.play_button.clicked.connect(self.toggle_play)

        layout = QVBoxLayout()
        layout.addWidget(self.play_button)
        self.setLayout(layout)

        self.audio_receiver = AudioReceiver()
        self.is_playing = False

    def toggle_play(self):
        if not self.is_playing:
            self.play_button.setText('Stop')
            # Tutaj można uruchomić odbieranie danych przez UDP
            self.audio_receiver.receive_audio()  # Rozpocznij odbieranie danych przez UDP
            self.is_playing = True
        else:
            self.play_button.setText('Play')
            # Tutaj można zatrzymać odbieranie danych przez UDP
            self.audio_receiver.close()  # Zatrzymaj odbieranie danych przez UDP
            self.is_playing = False

    def closeEvent(self, event):
        self.audio_receiver.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MusicPlayer()
    window.show()
    sys.exit(app.exec_())
