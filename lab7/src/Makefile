CC = gcc
CFLAGS = -Wall -g

all: tcpclient tcpserver udpclient udpserver

# === TCP ===
tcpclient: tcpclient.c
	$(CC) $(CFLAGS) -o tcpclient tcpclient.c

tcpserver: tcpserver.c
	$(CC) $(CFLAGS) -o tcpserver tcpserver.c

# === UDP ===
udpclient: udpclient.c
	$(CC) $(CFLAGS) -o udpclient udpclient.c

udpserver: udpserver.c
	$(CC) $(CFLAGS) -o udpserver udpserver.c

# === Очистка ===
clean:
	rm -f tcpclient tcpserver udpclient udpserver
