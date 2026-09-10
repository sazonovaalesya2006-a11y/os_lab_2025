CC = gcc
CFLAGS = -Wall -g -pthread

all: mutex_with_lock pfact deadlock_demo

mutex_with_lock: mutex.c
	$(CC) $(CFLAGS) -o mutex_with_lock mutex.c

pfact: parallel_factorial.c
	$(CC) $(CFLAGS) -o pfact parallel_factorial.c

deadlock_demo: deadlock_demo.c
	$(CC) $(CFLAGS) -o deadlock_demo deadlock_demo.c

clean:
	rm -f mutex_with_lock pfact deadlock_demo
