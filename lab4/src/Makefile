CC = gcc
CFLAGS = -Wall -g

# Цель по умолчанию: собрать обе программы
all: parallel_min_max process_memory

# Сборка parallel_min_max
parallel_min_max: parallel_min_max.c find_min_max.c utils.c
	$(CC) $(CFLAGS) -o parallel_min_max parallel_min_max.c find_min_max.c utils.c

# Сборка process_memory
process_memory: process_memory.c
	$(CC) $(CFLAGS) -o process_memory process_memory.c -w

# Очистка
clean:
	rm -f parallel_min_max process_memory
