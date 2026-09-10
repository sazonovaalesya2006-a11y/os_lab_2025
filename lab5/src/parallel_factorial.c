#include <sys/time.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <getopt.h>
#include <stdbool.h>

// Общий результат (факториал по модулю)
long long result = 1;

// Мьютекс для защиты критической секции (умножение результата)
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

// Аргументы для каждого потока
typedef struct {
    int start;
    int end;
    int mod;
} ThreadArgs;

// Функция потока: вычисляет произведение чисел в диапазоне [start, end] по модулю mod
void* thread_factorial(void* arg) {
    ThreadArgs* args = (ThreadArgs*)arg;
    long long local_product = 1;

    for (int i = args->start; i <= args->end; i++) {
        local_product = (local_product * i) % args->mod;
    }

    // === КРИТИЧЕСКАЯ СЕКЦИЯ ===
    // Умножаем общий результат на локальное произведение под защитой мьютекса
    pthread_mutex_lock(&mutex);
    result = (result * local_product) % args->mod;
    pthread_mutex_unlock(&mutex);
    // ==========================

    return NULL;
}

int main(int argc, char **argv) {
    int k = -1;
    int pnum = -1;
    int mod = -1;

    // Парсинг аргументов командной строки
    while (true) {
        static struct option options[] = {
            {"pnum", required_argument, 0, 0},
            {"mod", required_argument, 0, 0},
            {0, 0, 0, 0}
        };
        int option_index = 0;
        int c = getopt_long(argc, argv, "k:", options, &option_index);
        if (c == -1) break;
        switch (c) {
            case 0:
                switch (option_index) {
                    case 0: pnum = atoi(optarg); break;
                    case 1: mod = atoi(optarg); break;
                }
                break;
            case 'k':
                k = atoi(optarg);
                break;
            case '?':
                break;
            default:
                break;
        }
    }

    if (k <= 0 || pnum <= 0 || mod <= 0) {
        printf("Usage: %s -k \"num\" --pnum=\"num\" --mod=\"num\"\n", argv[0]);
        return 1;
    }

    // Начинаем замер времени
    struct timeval start_time, end_time;
    gettimeofday(&start_time, NULL);

    pthread_t *threads = malloc(pnum * sizeof(pthread_t));
    ThreadArgs *args = malloc(pnum * sizeof(ThreadArgs));

    // Разбиваем диапазон [1, k] на pnum частей
    int chunk_size = k / pnum;
    int remainder = k % pnum;
    int current_start = 1;

    for (int i = 0; i < pnum; i++) {
        args[i].start = current_start;
        args[i].end = current_start + chunk_size - 1;
        if (i == pnum - 1) {
            args[i].end += remainder; // Последний поток забирает остаток
        }
        args[i].mod = mod;

        current_start = args[i].end + 1;

        // Создание потока
        if (pthread_create(&threads[i], NULL, thread_factorial, &args[i]) != 0) {
            perror("pthread_create");
            return 1;
        }
    }

    // Ожидание завершения всех потоков
    for (int i = 0; i < pnum; i++) {
        pthread_join(threads[i], NULL);
    }

    // Завершаем замер времени
    gettimeofday(&end_time, NULL);

    double elapsed_time = (end_time.tv_sec - start_time.tv_sec) * 1000.0;
    elapsed_time += (end_time.tv_usec - start_time.tv_usec) / 1000.0;

    printf("%d! mod %d = %lld\n", k, mod, result);
    printf("Elapsed time: %fms\n", elapsed_time);

    free(threads);
    free(args);

    return 0;
}
