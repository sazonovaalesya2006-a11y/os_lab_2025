#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <errno.h>
#include <getopt.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/types.h>

// Описание одного сервера: IP-адрес и порт
struct Server {
  char ip[255];
  int port;
};

// Аргументы для одного клиентского потока.
// Каждый поток соединяется с ОДНИМ сервером и получает результат.
struct ClientArgs {
  struct Server server;   // адрес сервера, к которому надо подключиться
  uint64_t begin;         // начало диапазона для этого сервера
  uint64_t end;           // конец диапазона
  uint64_t mod;           // модуль
  uint64_t result;        // сюда запишем ответ от сервера
};

// Умножение по модулю без переполнения (см. server.c)
uint64_t MultModulo(uint64_t a, uint64_t b, uint64_t mod) {
  uint64_t result = 0;
  a = a % mod;
  while (b > 0) {
    if (b % 2 == 1) result = (result + a) % mod;
    a = (a * 2) % mod;
    b /= 2;
  }
  return result % mod;
}

// Преобразование строки в uint64_t с проверкой ошибок
bool ConvertStringToUI64(const char *str, uint64_t *val) {
  char *end = NULL;
  unsigned long long i = strtoull(str, &end, 10);
  if (errno == ERANGE) {
    fprintf(stderr, "Out of uint64_t range: %s\n", str);
    return false;
  }
  if (errno != 0) return false;
  *val = i;
  return true;
}

// === ФУНКЦИЯ ПОТОКА КЛИЕНТА ===
// Каждый поток:
//   1. Подключается к своему серверу.
//   2. Отправляет ему [begin, end, mod].
//   3. Получает ответ и сохраняет его в args->result.
// Именно это делает работу с серверами параллельной.
void *ClientThread(void *args) {
  struct ClientArgs *a = (struct ClientArgs *)args;

  // Преобразуем IP-адрес в понятный системе вид
  struct hostent *hostname = gethostbyname(a->server.ip);
  if (hostname == NULL) {
    fprintf(stderr, "gethostbyname failed with %s\n", a->server.ip);
    a->result = 1;   // нейтральный элемент по модулю (на случай ошибки)
    return NULL;
  }

  // Заполняем структуру с адресом сервера
  struct sockaddr_in server;
  server.sin_family = AF_INET;
  server.sin_port = htons(a->server.port);
  server.sin_addr.s_addr = *((unsigned long *)hostname->h_addr);

  // Создаём сокет для TCP
  int sck = socket(AF_INET, SOCK_STREAM, 0);
  if (sck < 0) {
    fprintf(stderr, "Socket creation failed!\n");
    a->result = 1;
    return NULL;
  }

  // Подключаемся к серверу
  if (connect(sck, (struct sockaddr *)&server, sizeof(server)) < 0) {
    fprintf(stderr, "Connection failed to %s:%d\n", a->server.ip, a->server.port);
    close(sck);
    a->result = 1;
    return NULL;
  }

  // Формируем пакет из трёх uint64_t: begin, end, mod
  char task[sizeof(uint64_t) * 3];
  memcpy(task, &a->begin, sizeof(uint64_t));
  memcpy(task + sizeof(uint64_t), &a->end, sizeof(uint64_t));
  memcpy(task + 2 * sizeof(uint64_t), &a->mod, sizeof(uint64_t));

  // Отправляем задачу серверу
  if (send(sck, task, sizeof(task), 0) < 0) {
    fprintf(stderr, "Send failed\n");
    close(sck);
    a->result = 1;
    return NULL;
  }

  // Получаем ответ (одно uint64_t)
  char response[sizeof(uint64_t)];
  if (recv(sck, response, sizeof(response), 0) < 0) {
    fprintf(stderr, "Receive failed\n");
    close(sck);
    a->result = 1;
    return NULL;
  }

  // Расшифровываем ответ и сохраняем
  memcpy(&a->result, response, sizeof(uint64_t));
  close(sck);
  return NULL;
}

int main(int argc, char **argv) {
  uint64_t k = (uint64_t)-1;       // до какого числа считать факториал
  uint64_t mod = (uint64_t)-1;     // модуль
  char servers[255] = {'\0'};      // путь до файла со списком серверов

  // === Парсинг аргументов: --k, --mod, --servers ===
  while (true) {
    static struct option options[] = {{"k", required_argument, 0, 0},
                                      {"mod", required_argument, 0, 0},
                                      {"servers", required_argument, 0, 0},
                                      {0, 0, 0, 0}};

    int option_index = 0;
    int c = getopt_long(argc, argv, "", options, &option_index);

    if (c == -1) break;

    switch (c) {
    case 0: {
      switch (option_index) {
      case 0:
        ConvertStringToUI64(optarg, &k);
        break;
      case 1:
        ConvertStringToUI64(optarg, &mod);
        break;
      case 2:
        // Копируем путь до файла серверов
        memcpy(servers, optarg, strlen(optarg));
        break;
      default:
        printf("Index %d is out of options\n", option_index);
      }
    } break;

    case '?':
      printf("Arguments error\n");
      break;
    default:
      fprintf(stderr, "getopt returned character code 0%o?\n", c);
    }
  }

  // Проверяем, что все аргументы переданы
  if (k == (uint64_t)-1 || mod == (uint64_t)-1 || !strlen(servers)) {
    fprintf(stderr, "Using: %s --k 1000 --mod 5 --servers /path/to/file\n",
            argv[0]);
    return 1;
  }

  // === Читаем список серверов из файла ===
  // Формат файла: одна строка = "ip:port"
  FILE *f = fopen(servers, "r");
  if (f == NULL) {
    fprintf(stderr, "Cannot open servers file: %s\n", servers);
    return 1;
  }

  struct Server *to = malloc(sizeof(struct Server) * 16);   // максимум 16 серверов
  unsigned int servers_num = 0;
  char line[300];

  // Читаем файл построчно
  while (fgets(line, sizeof(line), f) != NULL && servers_num < 16) {
    // Убираем символ перевода строки
    char *newline = strchr(line, '\n');
    if (newline) *newline = '\0';
    if (strlen(line) == 0) continue;  // пропускаем пустые строки

    // Ищем двоеточие, разделяющее ip и port
    char *colon = strchr(line, ':');
    if (colon == NULL) continue;
    *colon = '\0';  // разделяем строку: до '\0' — ip, после — port

    strncpy(to[servers_num].ip, line, sizeof(to[servers_num].ip) - 1);
    to[servers_num].ip[sizeof(to[servers_num].ip) - 1] = '\0';
    to[servers_num].port = atoi(colon + 1);
    servers_num++;
  }
  fclose(f);

  if (servers_num == 0) {
    fprintf(stderr, "No servers found in file\n");
    free(to);
    return 1;
  }

  printf("Found %u server(s)\n", servers_num);

  // === Распределяем диапазон [1, k] между серверами ===
  struct ClientArgs *args = malloc(sizeof(struct ClientArgs) * servers_num);
  pthread_t *threads = malloc(sizeof(pthread_t) * servers_num);

  uint64_t chunk_size = k / servers_num;
  uint64_t remainder = k % servers_num;
  uint64_t current_begin = 1;

  for (unsigned int i = 0; i < servers_num; i++) {
    args[i].begin = current_begin;
    args[i].end = current_begin + chunk_size - 1;
    if (i == servers_num - 1) {
      args[i].end += remainder;   // последний сервер получает остаток
    }
    args[i].mod = mod;
    args[i].server = to[i];
    args[i].result = 1;

    current_begin = args[i].end + 1;

    // === Запускаем поток, который обработает свой сервер параллельно ===
    if (pthread_create(&threads[i], NULL, ClientThread, &args[i]) != 0) {
      fprintf(stderr, "pthread_create failed\n");
      return 1;
    }
  }

  // === Ждём завершения всех потоков и перемножаем результаты по модулю ===
  // Здесь и получается итоговый ответ: k! mod mod
  uint64_t answer = 1;
  for (unsigned int i = 0; i < servers_num; i++) {
    pthread_join(threads[i], NULL);
    answer = MultModulo(answer, args[i].result, mod);
  }

  printf("answer: %llu\n", answer);

  // Освобождаем память
  free(threads);
  free(args);
  free(to);

  return 0;
}
