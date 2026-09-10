#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <getopt.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <sys/socket.h>
#include <sys/types.h>

#include "pthread.h"

// Структура с аргументами для одного потока:
// диапазон чисел [begin, end] и модуль mod
struct FactorialArgs {
  uint64_t begin;
  uint64_t end;
  uint64_t mod;
};

// Умножение по модулю без переполнения.
// Реализовано через "русское умножение" (сложение и удвоение),
// потому что прямое a*b может переполнить uint64_t.
uint64_t MultModulo(uint64_t a, uint64_t b, uint64_t mod) {
  uint64_t result = 0;
  a = a % mod;
  while (b > 0) {
    if (b % 2 == 1)
      result = (result + a) % mod;
    a = (a * 2) % mod;
    b /= 2;
  }
  return result % mod;
}

// Вычисляет произведение чисел от begin до end по модулю mod.
// Это и есть "кусок факториала", который считает один поток.
uint64_t Factorial(const struct FactorialArgs *args) {
  uint64_t ans = 1;
  if (args->begin > args->end) return 1;  // пустой диапазон = нейтральный элемент
  for (uint64_t i = args->begin; i <= args->end; i++) {
    ans = MultModulo(ans, i, args->mod);
  }
  return ans;
}

// Функция, которую выполняет каждый поток.
// Обёртка над Factorial, чтобы подходила под сигнатуру pthread.
void *ThreadFactorial(void *args) {
  struct FactorialArgs *fargs = (struct FactorialArgs *)args;
  return (void *)(uint64_t *)Factorial(fargs);
}

int main(int argc, char **argv) {
  int tnum = -1;   // количество потоков, которое будет использовать сервер
  int port = -1;   // порт, на котором слушает сервер

  // === Парсинг аргументов командной строки (--port и --tnum) ===
  while (true) {
    int current_optind = optind ? optind : 1;

    static struct option options[] = {{"port", required_argument, 0, 0},
                                      {"tnum", required_argument, 0, 0},
                                      {0, 0, 0, 0}};

    int option_index = 0;
    int c = getopt_long(argc, argv, "", options, &option_index);

    if (c == -1) break;  // закончились опции

    switch (c) {
    case 0: {
      switch (option_index) {
      case 0:
        port = atoi(optarg);
        break;
      case 1:
        tnum = atoi(optarg);
        break;
      default:
        printf("Index %d is out of options\n", option_index);
      }
    } break;

    case '?':
      printf("Unknown argument\n");
      break;
    default:
      fprintf(stderr, "getopt returned character code 0%o?\n", c);
    }
  }

  // Проверяем, что все параметры заданы
  if (port == -1 || tnum == -1) {
    fprintf(stderr, "Using: %s --port 20001 --tnum 4\n", argv[0]);
    return 1;
  }

  // === Создаём TCP-сокет ===
  // AF_INET — IPv4, SOCK_STREAM — TCP
  int server_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (server_fd < 0) {
    fprintf(stderr, "Can not create server socket!");
    return 1;
  }

  // Заполняем структуру с адресом сервера
  struct sockaddr_in server;
  server.sin_family = AF_INET;
  server.sin_port = htons((uint16_t)port);       // htons — конвертирует порт в сетевой порядок байт
  server.sin_addr.s_addr = htonl(INADDR_ANY);    // INADDR_ANY — слушать на всех интерфейсах

  // Разрешаем переиспользовать адрес (чтобы не было ошибки "Address already in use")
  int opt_val = 1;
  setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt_val, sizeof(opt_val));

  // === Привязываем сокет к порту ===
  int err = bind(server_fd, (struct sockaddr *)&server, sizeof(server));
  if (err < 0) {
    fprintf(stderr, "Can not bind to socket!");
    return 1;
  }

  // === Начинаем слушать входящие соединения ===
  // 128 — размер очереди ожидающих соединений
  err = listen(server_fd, 128);
  if (err < 0) {
    fprintf(stderr, "Could not listen on socket\n");
    return 1;
  }

  printf("Server listening at %d\n", port);

  // === Основной цикл сервера: принимаем соединения одно за другим ===
  while (true) {
    struct sockaddr_in client;
    socklen_t client_len = sizeof(client);

    // accept — блокируется, пока не придёт новый клиент.
    // Возвращает новый сокет для общения именно с этим клиентом.
    int client_fd = accept(server_fd, (struct sockaddr *)&client, &client_len);

    if (client_fd < 0) {
      fprintf(stderr, "Could not establish new connection\n");
      continue;
    }

    // Внутренний цикл: пока клиент присылает задачи, обрабатываем их
    while (true) {
      // Ожидаем ровно 3 uint64_t: begin, end, mod
      unsigned int buffer_size = sizeof(uint64_t) * 3;
      char from_client[buffer_size];
      int read_bytes = recv(client_fd, from_client, buffer_size, 0);

      if (!read_bytes) break;                // клиент закрыл соединение
      if (read_bytes < 0) {
        fprintf(stderr, "Client read failed\n");
        break;
      }
      if (read_bytes < (int)buffer_size) {   // получили меньше, чем ожидали
        fprintf(stderr, "Client send wrong data format\n");
        break;
      }

      pthread_t threads[tnum];

      // Извлекаем три числа из полученного буфера
      uint64_t begin = 0;
      uint64_t end = 0;
      uint64_t mod = 0;
      memcpy(&begin, from_client, sizeof(uint64_t));
      memcpy(&end, from_client + sizeof(uint64_t), sizeof(uint64_t));
      memcpy(&mod, from_client + 2 * sizeof(uint64_t), sizeof(uint64_t));

      fprintf(stdout, "Receive: %llu %llu %llu\n", begin, end, mod);

      // === Разбиваем диапазон [begin, end] между tnum потоками ===
      struct FactorialArgs args[tnum];
      uint64_t total_count = end - begin + 1;
      uint64_t chunk_size = total_count / tnum;
      uint64_t remainder = total_count % tnum;
      uint64_t current_begin = begin;

      for (uint32_t i = 0; i < (uint32_t)tnum; i++) {
        args[i].begin = current_begin;
        args[i].end = current_begin + chunk_size - 1;
        if (i == (uint32_t)(tnum - 1)) {
          args[i].end += remainder;   // последний поток забирает остаток
        }
        args[i].mod = mod;
        current_begin = args[i].end + 1;

        // Создаём поток, который посчитает свою часть
        if (pthread_create(&threads[i], NULL, ThreadFactorial,
                           (void *)&args[i])) {
          printf("Error: pthread_create failed!\n");
          return 1;
        }
      }

      // === Собираем результаты всех потоков и перемножаем их по модулю ===
      uint64_t total = 1;
      for (uint32_t i = 0; i < (uint32_t)tnum; i++) {
        uint64_t result = 0;
        pthread_join(threads[i], (void **)&result);
        total = MultModulo(total, result, mod);
      }

      printf("Total: %llu\n", total);

      // Отправляем результат обратно клиенту
      char buffer[sizeof(total)];
      memcpy(buffer, &total, sizeof(total));
      err = send(client_fd, buffer, sizeof(total), 0);
      if (err < 0) {
        fprintf(stderr, "Can't send data to client\n");
        break;
      }
    }

    // Закрываем соединение с клиентом
    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);
  }

  return 0;
}
