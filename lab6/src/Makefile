CC = gcc
CFLAGS = -Wall -g -pthread

# Цель по умолчанию: собрать и сервер, и клиент
all: server client

# Сборка сервера
server: server.c
	$(CC) $(CFLAGS) -o server server.c

# Сборка клиента
client: client.c
	$(CC) $(CFLAGS) -o client client.c

# Очистка: удаляем бинарники
clean:
	rm -f server client
