import pygame
import socket

def play_music(byte_stream):
    pygame.init()
    pygame.mixer.init()
    sound = pygame.mixer.Sound(byte_stream)
    sound.play()

UDP_IP = "127.0.0.1"  # Tutaj wpisz odpowiedni adres IP
UDP_PORT = 12345       # Tutaj wpisz odpowiedni port

# Tworzymy gniazdo UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print("Oczekiwanie na dane...")

while True:
    data, addr = sock.recvfrom(1024)  # Odbieramy dane z gniazda UDP
    print(f"Otrzymano dane od {addr}")
    
    # Odtwarzamy muzykę na podstawie otrzymanych danych bajtowych
    play_music(data)
