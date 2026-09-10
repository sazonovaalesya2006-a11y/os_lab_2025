CC = gcc
CFLAGS = -Wall -g -pthread

all: server client

# === Создание статической библиотеки libcommon.a из common.o ===
libcommon.a: common.o
	ar rcs libcommon.a common.o

# Компиляция common.c в объектный файл
common.o: common.c common.h
	$(CC) $(CFLAGS) -c common.c -o common.o

# Сборка сервера: линкуем с libcommon.a (ищем её в текущей папке -L.)
server: server.c libcommon.a
	$(CC) $(CFLAGS) -o server server.c -L. -lcommon

# Сборка клиента: линкуем с libcommon.a
client: client.c libcommon.a
	$(CC) $(CFLAGS) -o client client.c -L. -lcommon

# Очистка: удаляем бинарники, объектные файлы и саму библиотеку
clean:
	rm -f server client common.o libcommon.a
