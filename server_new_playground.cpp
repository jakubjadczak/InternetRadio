// WARNING - HAVEN'T TESTED IT SO BE SUPERCAREFULL KUBA PLZ
// And yeah so sorry for pushing to main XD
/*
[fixed] binarek nie powinno być na repo (a.out)
[fixed] brakuje Makefile/… dla serwera
[work in progress] main.cpp:58 handleClientData - nie ma jeszcze wsparcia dla podziału/sklejenia komunikatów od klienta
[fixed] sendChunkToClient - w trybie blokującym pętla z l90 wykona się raz, w nieblokującym albo raz, a jeśli drugi, to drugi send się nie powiedzie; po co ta pętla?  -> usunięto pętle
[fixed] main.cpp:123 zgaduję że wysyłacie kawałki po 2 sekundy; lepiej zapisać czas początku funkcji i czekać do czas+2s, np. auto time = std::chrono::steady_clock::now(); i std::this_thread::sleep_until(time+=std::chrono::seconds(2));, inaczej będzie się rozjeżdżać o czas wykonywania wysłania danych
[chyba fixed] ostatni kawałek piosenki wymaga mniej czasu oczekiwania - nie każda piosenka jest podzielna przez 2s bez reszty.
[fixed] handleStreamingRequests - rozumiem że później przepiszecie projekt na wątki, tak żeby nie było wysłania po kolei do klientów, tylko naraz do klientów

! Wprowadzono wątki, czy i jak działają nie wiem. Ale wyglądają przyzwoicie.
! Wprowadzono mutex w funkcji handleStreamingRequests aby zabezpieczyć operacje na kolejce - problem równoczesnego dostępu.
*/

//Program czyta liste utworow i na zadanie klienta wysyla
//Klient ustawia je w liste(drag&drop)
//W tej kwestii zostalo jeszcze wysylanie updatowanej listy do serwera


#include <iostream>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/poll.h>
#include <vector>
#include <string>
#include <dirent.h>
#include <fstream>
#include <queue>
#include <algorithm>
#include <thread>
#include <chrono>
#include <mutex>
#include <filesystem>

#define PORT 8082
#define MAX_CLIENTS 10
#define BUFFER_SIZE 192000
#define SONGS_DIR "songs"

std::mutex clientsMutex;

namespace fs = std::filesystem;

std::vector<std::string> getFilenamesInDirectory(const std::string& directory) {
    std::vector<std::string> filenames;
    try {
        // Sprawdzenie, czy podana ścieżka jest katalogiem
        if (fs::is_directory(directory)) {
            for (const auto& entry : fs::directory_iterator(directory)) {
                // Sprawdzenie, czy element jest plikiem
                if (entry.is_regular_file()) {
                    filenames.push_back(entry.path().filename().string());
                }
            }
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "Błąd przy odczycie katalogu: " << e.what() << '\n';
    }

    return filenames;
}

void createServerSocket(int& serverSocket) {
    if ((serverSocket = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Błąd przy tworzeniu gniazda serwera");
        exit(EXIT_FAILURE);
    }
}

void bindServerSocket(int serverSocket) {
    struct sockaddr_in serverAddr;

    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(PORT);
    serverAddr.sin_addr.s_addr = INADDR_ANY;

    if (bind(serverSocket, (struct sockaddr *)&serverAddr, sizeof(serverAddr)) == -1) {
        perror("Błąd przy przypisywaniu adresu i portu");
        close(serverSocket);
        exit(EXIT_FAILURE);
    }
}

void listenForConnections(int serverSocket) {
    if (listen(serverSocket, MAX_CLIENTS) == -1) {
        perror("Błąd przy nasłuchiwaniu");
        close(serverSocket);
        exit(EXIT_FAILURE);
    }
    std::cout << "Serwer nasłuchuje na porcie " << PORT << "..." << std::endl;
}

int handleNewConnection(int serverSocket) {
    struct sockaddr_in clientAddr;
    socklen_t addrSize = sizeof(struct sockaddr_in);
    int newSocket = accept(serverSocket, (struct sockaddr *)&clientAddr, &addrSize);
    std::cout << "Nawiązano połączenie z klientem: " << inet_ntoa(clientAddr.sin_addr) << std::endl;
    return newSocket;
}

void sendChunkToClient(int clientSocket, const char* chunk, size_t chunkSize) {
    size_t totalBytesSent = 0;

    while (totalBytesSent < chunkSize) {
        ssize_t sent = send(clientSocket, chunk + totalBytesSent, chunkSize - totalBytesSent, 0);

        if (sent == -1) {
            std::cerr << "Błąd przy wysyłaniu danych do klienta" << std::endl;
            break;
        }
        totalBytesSent += sent;
    }
}

void broadcastChunksForClient(int clientSocket) {
    DIR* dir;
    struct dirent* ent;

    if ((dir = opendir(SONGS_DIR)) != nullptr) {
        while ((ent = readdir(dir)) != nullptr) {
            if (ent->d_type == DT_REG) {
                std::string filePath = std::string(SONGS_DIR) + "/" + ent->d_name;
                std::ifstream file(filePath, std::ios::binary);

                if (!file) {
                    std::cerr << "Błąd przy otwieraniu pliku: " << filePath << std::endl;
                    continue;
                }

                char buffer[BUFFER_SIZE];

                auto startTime = std::chrono::steady_clock::now();

                while (!file.eof()) {
                    file.read(buffer, sizeof(buffer));
                    size_t bytesRead = file.gcount();
                
                    sendChunkToClient(clientSocket, buffer, bytesRead);
                
                    auto currentTime = std::chrono::steady_clock::now();
                    auto elapsedTime = std::chrono::duration_cast<std::chrono::seconds>(currentTime - startTime);
                    auto sleepTime = startTime + std::chrono::seconds(2);
                
                    if (elapsedTime < std::chrono::seconds(2)) {
                        std::this_thread::sleep_for(std::chrono::seconds(2) - elapsedTime);
                    }
                
                    startTime = std::chrono::steady_clock::now();
                }

                file.close();
            }
        }
        closedir(dir);
    } else {
        perror("Błąd przy otwieraniu katalogu");
    }
}

void handleClientRequest(int clientSocket) {
    char buffer[1024];
    ssize_t bytesReceived = recv(clientSocket, buffer, sizeof(buffer), 0);
    if (bytesReceived > 0) {
        std::string request(buffer, bytesReceived);
        if (request == "SongsList") {
            std::string header = "LIST:\n";
            send(clientSocket, header.c_str(), header.size(), 0);

            std::vector<std::string> filenames = getFilenamesInDirectory("songs");
            std::vector<std::string> strings = filenames;
            for (const auto& str : strings) {
                std::string response = str + "\n";
                send(clientSocket, response.c_str(), response.size(), 0);
            }
            std::cout << "Wyslano liste" << std::endl;
        }
    }
}


void handleStreamingRequests(int serverSocket) {
    while (true) {
        int clientSocket = handleNewConnection(serverSocket);

        std::thread([serverSocket, clientSocket]() {
            std::lock_guard<std::mutex> lock(clientsMutex);
            handleClientRequest(clientSocket);
            broadcastChunksForClient(clientSocket);
            close(clientSocket);
        }).detach();
    }
}


int main() {
    int serverSocket;
    createServerSocket(serverSocket);
    bindServerSocket(serverSocket);
    listenForConnections(serverSocket);

    std::vector<std::string> strings = {"Hello", "World", "!"};

    handleStreamingRequests(serverSocket);

    close(serverSocket);
    std::cout << "Serwer zakończył działanie." << std::endl;
    return 0;
}

