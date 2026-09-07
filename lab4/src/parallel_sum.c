#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <getopt.h>
#include <stdbool.h>
#include <sys/time.h>
#include <string.h>

#include "utils.h"
#include "sum_lib.h"

typedef struct {
    const int *array;
    size_t start;
    size_t end;
    long long sum;
} ThreadArgs;

// Функция, которую выполняет каждый поток
void* thread_sum(void* arg) {
    ThreadArgs* args = (ThreadArgs*)arg;
    args->sum = calculate_sum(args->array, args->start, args->end);
    return NULL;
}

int main(int argc, char **argv) {
    int seed = -1;
    int array_size = -1;
    int threads_num = -1;

    // Парсинг аргументов командной строки
    while (true) {
        static struct option options[] = {
            {"seed", required_argument, 0, 0},
            {"array_size", required_argument, 0, 0},
            {"threads_num", required_argument, 0, 0},
            {0, 0, 0, 0}
        };
        int option_index = 0;
        int c = getopt_long(argc, argv, "", options, &option_index);
        if (c == -1) break;
        switch (c) {
            case 0:
                switch (option_index) {
                    case 0: seed = atoi(optarg); break;
                    case 1: array_size = atoi(optarg); break;
                    case 2: threads_num = atoi(optarg); break;
                }
                break;
            case '?':
                break;
            default:
                break;
        }
    }

    if (seed == -1 || array_size == -1 || threads_num == -1) {
        printf("Usage: %s --seed \"num\" --array_size \"num\" --threads_num \"num\"\n", argv[0]);
        return 1;
    }

    // Генерация массива (НЕ входит в замер времени!)
    int *array = malloc(array_size * sizeof(int));
    GenerateArray(array, array_size, seed);

    // Начинаем замер времени
    struct timeval start_time, end_time;
    gettimeofday(&start_time, NULL);

    pthread_t *threads = malloc(threads_num * sizeof(pthread_t));
    ThreadArgs *args = malloc(threads_num * sizeof(ThreadArgs));

    int chunk_size = array_size / threads_num;
    int remainder = array_size % threads_num;

    // Создание потоков
    for (int i = 0; i < threads_num; ++i) {
        args[i].array = array;
        args[i].start = i * chunk_size;
        args[i].end = args[i].start + chunk_size;
        if (i == threads_num - 1) {
            args[i].end += remainder; // Последний поток забирает остаток
        }
        pthread_create(&threads[i], NULL, thread_sum, &args[i]);
    }

    // Ожидание завершения всех потоков и сбор результатов
    long long total_sum = 0;
    for (int i = 0; i < threads_num; ++i) {
        pthread_join(threads[i], NULL);
        total_sum += args[i].sum;
    }

    // Завершаем замер времени
    gettimeofday(&end_time, NULL);

    double elapsed_time = (end_time.tv_sec - start_time.tv_sec) * 1000.0;
    elapsed_time += (end_time.tv_usec - start_time.tv_usec) / 1000.0;

    printf("Sum: %lld\n", total_sum);
    printf("Elapsed time: %fms\n", elapsed_time);

    // Освобождаем память
    free(threads);
    free(args);
    free(array);

    return 0;
}
