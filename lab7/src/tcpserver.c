#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include <getopt.h>

#define SADDR struct sockaddr

int main(int argc, char *argv[]) {
  // Значения по умолчанию (раньше были #define)
  int serv_port = 10050;
  int bufsize = 100;

  // === Парсинг аргументов командной строки ===
  while (1) {
    static struct option options[] = {
        {"port",    required_argument, 0, 'p'},
        {"bufsize", required_argument, 0, 'b'},
        {0, 0, 0, 0}};
    int c = getopt_long(argc, argv, "p:b:", options, NULL);
    if (c == -1) break;
    switch (c) {
      case 'p': serv_port = atoi(optarg); break;
      case 'b': bufsize = atoi(optarg); break;
    }
  }

  const size_t kSize = sizeof(struct sockaddr_in);

  int lfd, cfd;
  int nread;
  char *buf = malloc(bufsize);   // буфер в куче, т.к. размер задаётся аргументом
  struct sockaddr_in servaddr;
  struct sockaddr_in cliaddr;

  // === Создание TCP-сокета ===
  if ((lfd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
    perror("socket");
    exit(1);
  }

  // Настраиваем адрес сервера
  memset(&servaddr, 0, kSize);
  servaddr.sin_family = AF_INET;
  servaddr.sin_addr.s_addr = htonl(INADDR_ANY);   // слушаем на всех интерфейсах
  servaddr.sin_port = htons(serv_port);

  // === Привязка сокета к порту ===
  if (bind(lfd, (SADDR *)&servaddr, kSize) < 0) {
    perror("bind");
    exit(1);
  }

  // === Начинаем слушать ===
  if (listen(lfd, 5) < 0) {
    perror("listen");
    exit(1);
  }

  printf("TCP server listening at port %d (bufsize=%d)\n", serv_port, bufsize);

  // === Основной цикл: принимаем клиентов по одному ===
  while (1) {
    unsigned int clilen = kSize;

    if ((cfd = accept(lfd, (SADDR *)&cliaddr, &clilen)) < 0) {
      perror("accept");
      exit(1);
    }
    printf("connection established\n");

    // Читаем всё, что присылает клиент, и выводим на экран
    while ((nread = read(cfd, buf, bufsize)) > 0) {
      write(1, buf, nread);
    }

    if (nread == -1) {
      perror("read");
      exit(1);
    }
    close(cfd);
  }

  free(buf);
}
