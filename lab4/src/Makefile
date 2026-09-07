CC = gcc
CFLAGS = -Wall -g -pthread

all: psum

psum: parallel_sum.c sum_lib.c sum_lib.h utils.c utils.h
	$(CC) $(CFLAGS) -o psum parallel_sum.c sum_lib.c utils.c

clean:
	rm -f psum
