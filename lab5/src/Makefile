CC = gcc
CFLAGS = -Wall -g -pthread

all: mutex_with_lock pfact

mutex_with_lock: mutex.c
	$(CC) $(CFLAGS) -o mutex_with_lock mutex.c

pfact: parallel_factorial.c
	$(CC) $(CFLAGS) -o pfact parallel_factorial.c

clean:
	rm -f mutex_with_lock pfact
