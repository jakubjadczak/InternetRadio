#include <iostream>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/poll.h>
#include <vector>
#include <dirent.h>
#include <fstream>
#include <queue>
#include <algorithm>
#include <thread>
#include <chrono>


#define PORT 8082
#define MAX_CLIENTS 10
#define BUFFER_SIZE 50000
#define SONGS_DIR "songs"

int serverSocket;
std::queue<int> clientsWaitingForStream;

void createServerSocket() {
    if ((serverSocket = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Błąd przy tworzeniu gniazda serwera");
        exit(EXIT_FAILURE);
    }
}
void bindServerSocket() {
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
void listenForConnections() {
    if (listen(serverSocket, MAX_CLIENTS) == -1) {
        perror("Błąd przy nasłuchiwaniu");
        close(serverSocket);
        exit(EXIT_FAILURE);
    }
    std::cout << "Serwer nasłuchuje na porcie " << PORT << "..." << std::endl;
}

int handleNewConnection() {
    struct sockaddr_in clientAddr;
    socklen_t addrSize = sizeof(struct sockaddr_in);
    int newSocket = accept(serverSocket, (struct sockaddr *)&clientAddr, &addrSize);
    std::cout << "Nawiązano połączenie z klientem: " << inet_ntoa(clientAddr.sin_addr) << std::endl;
    return newSocket;
}
void handleClientData(pollfd& fd, std::vector<pollfd>& fds) {
    std::cout<< "1 \n ";

    char buffer[BUFFER_SIZE];
    ssize_t bytesRead = recv(fd.fd, buffer, sizeof(buffer), 0);

    if (bytesRead <= 0) {
        std::cout<< "2\n ";
        std::cerr << "Błąd przy odbieraniu danych lub klient zakończył połączenie" << std::endl;
        close(fd.fd);
        fds.erase(std::remove_if(fds.begin(), fds.end(),
                                 [&fd](const pollfd& p) { return p.fd == fd.fd; }), fds.end());
    } else {
        std::cout<< "3\n";
        std::string request(buffer, bytesRead);
        std::cout<< request << std::endl;
        if (request == "request_stream") {
            std::cout<< "request stream \n ";
            clientsWaitingForStream.push(fd.fd);
        } else if(request == "test"){
            std::cout<< "test\n ";
            send(fd.fd, "test ok", 7, 0);
        }
        else {
            std::cerr << "Nieznane żądanie: " << request << std::endl;
        }
    }
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

                while (!file.eof()) {
                    file.read(buffer, sizeof(buffer));
                    size_t bytesRead = file.gcount();

                    sendChunkToClient(clientSocket, buffer, bytesRead);

                    std::this_thread::sleep_for(std::chrono::seconds(2));
                }
                file.close();
            }
        }
        closedir(dir);
    } else {
        perror("Błąd przy otwieraniu katalogu");
    }
}

void handleStreamingRequests(std::vector<pollfd>& fds) {
    while (!clientsWaitingForStream.empty()) {
        int clientSocket = clientsWaitingForStream.front();
        clientsWaitingForStream.pop();
        broadcastChunksForClient(clientSocket);
    }
}


int main() {
    std::vector<pollfd> fds;

    createServerSocket();
    bindServerSocket();
    listenForConnections();

    fds.push_back({serverSocket, POLLIN, 0});

    while (true) {
        int result = poll(fds.data(), fds.size(), -1);

        if (result == -1) {
            perror("Błąd przy użyciu poll");
            break;
        }

        for (auto& fd : fds) {
            if (fd.revents & POLLIN) {
                if (fd.fd == serverSocket) {
                    int newClientSocket = handleNewConnection();
                    fds.push_back({newClientSocket, POLLIN, 0});
                } else {
                    handleClientData(fd, fds);
                }
            }
        }
        handleStreamingRequests(fds);
    }
    for (auto& fd : fds) {
        close(fd.fd);
    }
    std::cout << "Serwer zakończył działanie." << std::endl;
    return 0;
}
