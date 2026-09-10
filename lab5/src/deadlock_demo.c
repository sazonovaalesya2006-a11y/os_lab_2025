#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>

// Два мьютекса (два ресурса)
pthread_mutex_t mutex1 = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t mutex2 = PTHREAD_MUTEX_INITIALIZER;

// Поток 1: сначала захватывает mutex1, потом mutex2
void* thread1_func(void* arg) {
    printf("Поток 1: пытается захватить mutex1...\n");
    pthread_mutex_lock(&mutex1);
    printf("Поток 1: захватил mutex1\n");

    // Небольшая задержка, чтобы другой поток успел захватить mutex2
    sleep(1);

    printf("Поток 1: пытается захватить mutex2...\n");
    pthread_mutex_lock(&mutex2);
    printf("Поток 1: захватил mutex2\n");

    // Этот код никогда не выполнится, если случится deadlock
    pthread_mutex_unlock(&mutex2);
    pthread_mutex_unlock(&mutex1);
    printf("Поток 1: освободил оба мьютекса\n");
    return NULL;
}

// Поток 2: сначала захватывает mutex2, потом mutex1
void* thread2_func(void* arg) {
    printf("Поток 2: пытается захватить mutex2...\n");
    pthread_mutex_lock(&mutex2);
    printf("Поток 2: захватил mutex2\n");

    // Небольшая задержка, чтобы другой поток успел захватить mutex1
    sleep(1);

    printf("Поток 2: пытается захватить mutex1...\n");
    pthread_mutex_lock(&mutex1);
    printf("Поток 2: захватил mutex1\n");

    pthread_mutex_unlock(&mutex1);
    pthread_mutex_unlock(&mutex2);
    printf("Поток 2: освободил оба мьютекса\n");
    return NULL;
}

int main() {
    pthread_t thread1, thread2;

    printf("=== Демонстрация Deadlock ===\n");
    printf("Два потока захватывают два мьютекса в разном порядке.\n\n");

    // Создаем оба потока
    pthread_create(&thread1, NULL, thread1_func, NULL);
    pthread_create(&thread2, NULL, thread2_func, NULL);

    // Ожидаем завершения потоков
    pthread_join(thread1, NULL);
    pthread_join(thread2, NULL);

    printf("\n=== Программа завершена (это сообщение вы не увидите при deadlock!) ===\n");
    return 0;
}
