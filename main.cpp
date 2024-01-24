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
#include <list>
#include <fcntl.h>
#include <sstream>
#include <utility>
#include <functional>


#define PORT 8080
#define MAX_CLIENTS 10
#define BUFFER_SIZE 32000
#define SONGS_DIR "songs"

std::mutex clientsMutex;
std::mutex songsListMutex;
std::list<std::string> SongsList;
std::vector<int> clientSockets;

namespace fs = std::filesystem;

struct ClientState {
    bool upload;
    std::ofstream outputFile;
};

std::list<std::pair<int, ClientState>> clientList;

void addNewClient(int clientSocket) {
    ClientState initialState; // Tworzy początkowy stan dla nowego klienta
    initialState.upload = false; // Ustawienie domyślnych wartości
    clientList.emplace_back(clientSocket, ClientState{});
}

void removeClient(int clientSocket) {
    clientList.remove_if([clientSocket](const std::pair<int, ClientState>& clientPair) {
        return clientPair.first == clientSocket;
    });
}


void getFilenamesInDirectory(const std::string& directory) {
    try {
        // Sprawdzenie, czy podana ścieżka jest katalogiem
        if (fs::is_directory(directory)) {
            SongsList.clear(); // Wyczyść aktualną listę przed dodaniem nowych elementów
            for (const auto& entry : fs::directory_iterator(directory)) {
                // Sprawdzenie, czy element jest plikiem
                if (entry.is_regular_file()) {
                    SongsList.push_back(entry.path().filename().string());
                }
            }
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "Błąd przy odczycie katalogu: " << e.what() << '\n';
    }
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

bool sendChunkToClient(int clientSocket, const char* chunk, size_t chunkSize) {
    size_t totalBytesSent = 0;

    while (totalBytesSent < chunkSize) {
        ssize_t sent = send(clientSocket, chunk + totalBytesSent, chunkSize - totalBytesSent, 0);

        if (sent == -1) {
            std::cerr << "Błąd przy wysyłaniu danych do klienta" << std::endl;
            return false;
        }
        totalBytesSent += sent;
    }
    return true;
}

void broadcastChunksForClient(int clientSocket) {
    auto it = SongsList.begin();

    while (true) {
        std::string currentSong;

        {
            std::lock_guard<std::mutex> lock(songsListMutex);
            if (it == SongsList.end()) {
                // Jeśli iterator doszedł do końca listy, zaczynamy od początku.
                it = SongsList.begin();
                // Jeśli lista jest pusta, wychodzimy z pętli.
                if (it == SongsList.end()) {
                    break;
                }
            }
            currentSong = *it;
        }

        std::string filePath = std::string(SONGS_DIR) + "/" + currentSong;
        std::ifstream file(filePath, std::ios::binary);

        if (!file) {
            std::cerr << "Błąd przy otwieraniu pliku: " << filePath << std::endl;
            // Przechodzimy do następnej piosenki, nawet jeśli ta nie mogła zostać otwarta.
            std::lock_guard<std::mutex> lock(songsListMutex);
            if (++it == SongsList.end() && !SongsList.empty()) {
                it = SongsList.begin();
            }
            continue;
        }

        char buffer[BUFFER_SIZE];
        while (!file.eof()) {
            file.read(buffer, sizeof(buffer));
            size_t bytesRead = file.gcount();

            bool sentOk = sendChunkToClient(clientSocket, buffer, bytesRead);
            std::this_thread::sleep_for(std::chrono::milliseconds(1300));
            if (!sentOk) {
                return;
            }
        }
        file.close();

        // Przechodzimy do następnej piosenki
        std::lock_guard<std::mutex> lock(songsListMutex);
        if (++it == SongsList.end() && !SongsList.empty()) {
            it = SongsList.begin();
        }
    }
}


void updateSongsListAndNotifyClients() {
    getFilenamesInDirectory(SONGS_DIR);
    // Wysyłanie zaktualizowanej listy do wszystkich klientów

    std::string header = "LIST:\n";
    std::string listContent;

    // Budowanie listy piosenek do wysłania
    for (const auto& song : SongsList) {
        listContent += song + "\n";
    }

    std::string fullMessage = header + listContent ;

    // Wysyłanie zaktualizowanej listy do wszystkich klientów
    std::lock_guard<std::mutex> lock(clientsMutex);
    std::cout << "Size: " << clientSockets.size() << std::endl;
    for (int clientSocket : clientSockets) {
        std::cout << "Sending list " << std::endl;
        send(clientSocket, fullMessage.c_str(), fullMessage.size(), 0);
    }
}
void setSocketNonBlocking(int socket) {
    int flags = fcntl(socket, F_GETFL, 0);
    if (flags == -1) {
        std::cerr << "Nie można pobrać flag gniazda" << std::endl;
        return;
    }
    flags |= O_NONBLOCK;
    if (fcntl(socket, F_SETFL, flags) == -1) {
        std::cerr << "Nie można ustawić gniazda na nieblokujące" << std::endl;
    }
}

bool processClientRequest(int clientSocket) {
    char buffer[1024];
    memset(buffer, 0, 1024);
    ssize_t bytesReceived = recv(clientSocket, buffer, sizeof(buffer), 0);
    std::cout << "Buffer: " << buffer << std::endl;

    if (bytesReceived <= 0) {
        // Zakończ, jeśli nie ma danych do odczytu lub wystąpił błąd
        close(clientSocket); // Zamknij gniazdo klienta
        std::cout << "Klient rozłączył się." << std::endl;
        return true;
    }
    std::string request(buffer, bytesReceived);

    for (auto& clientPair : clientList) {
        if (clientPair.first == clientSocket) {
            ClientState& state = clientPair.second;

            if (request == "SongsList") {
                getFilenamesInDirectory(SONGS_DIR);
                std::string header = "LIST:\n";
                std::string listContent;
                for (const auto& song : SongsList) {
                    listContent += song + "\n";
                }
                std::string fullMessage = header + listContent ;
                send(clientSocket, fullMessage.c_str(), fullMessage.size(), 0);
                std::cout << "Wysłano listę" << std::endl;
            } else if (request.rfind("UpdateOrder:", 0) == 0) {
                std::string orderStr = request.substr(12); // Usuń "UpdateOrder:"
                std::istringstream iss(orderStr);
                std::string song;
                SongsList.clear();
                while (std::getline(iss, song, ',')) {
                    SongsList.push_back(song);
                }
                std::cout << "Otrzymano i zaktualizowano kolejność utworów" << std::endl;
            } else if (request == "request_stream") {
                std::thread([clientSocket]() {
                    broadcastChunksForClient(clientSocket);
                    close(clientSocket); // Zamknij gniazdo po zakończeniu strumieniowania
                }).detach();
            } else if (request.find("BeginFileUpload:") == 0) {
                state.upload = true;
                std::string fileName = request.substr(16); // Pobierz nazwę pliku
                std::filesystem::path filePath = std::filesystem::path(SONGS_DIR) / fileName;
                state.outputFile.open(filePath, std::ios::binary);
            } else if (request.find("EndFileUpload") == 0) {
                state.upload = false;
                state.outputFile.close();
                updateSongsListAndNotifyClients();
            } else if (state.upload) {
                state.outputFile.write(buffer, bytesReceived);
            } else {
                std::cerr << "Otrzymano nieznane żądanie: " << request << std::endl;
            }
            break;
        }
    }
    return false;
}

void handleConnections(int serverSocket) {
    fd_set readfds;

    while (true) {
        FD_ZERO(&readfds);
        FD_SET(serverSocket, &readfds);
        int max_sd = serverSocket;

        for (int socket : clientSockets) {
            FD_SET(socket, &readfds);
            if (socket > max_sd) {
                max_sd = socket;
            }
        }

        int activity = select(max_sd + 1, &readfds, NULL, NULL, NULL);
        if ((activity < 0) && (errno != EINTR)) {
            std::cout << "Błąd funkcji select" << std::endl;
        }

        // Nowe połączenie
        if (FD_ISSET(serverSocket, &readfds)) {
            int newSocket = handleNewConnection(serverSocket);
            addNewClient(newSocket); // Dodaj nowego klienta
            setSocketNonBlocking(newSocket);
            clientSockets.push_back(newSocket);

        }
        // Aktywność na jednym z klientów
        for (int i = 0; i < clientSockets.size(); i++) {
            int clientSocket = clientSockets[i];
            if (FD_ISSET(clientSocket, &readfds)) {
                if (processClientRequest(clientSocket)) {
                    removeClient(clientSocket); // Usuń klienta, jeśli rozłączony
                    close(clientSocket); // Zamknij gniazdo klienta
                    clientSockets.erase(clientSockets.begin() + i); // Usuń gniazdo z listy
                    i--; // Zmniejsz indeks, ponieważ lista została zmodyfikowana
                }
            }
        }
    }
}


int main() {
    int serverSocket;
    createServerSocket(serverSocket);
    setSocketNonBlocking(serverSocket);
    bindServerSocket(serverSocket);
    listenForConnections(serverSocket);

    handleConnections(serverSocket);

    close(serverSocket);
    std::cout << "Serwer zakończył działanie." << std::endl;
    return 0;
}
