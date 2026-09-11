#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include <getopt.h>

#define SADDR struct sockaddr
#define SIZE sizeof(struct sockaddr_in)

int main(int argc, char *argv[]) {
  // Значения по умолчанию (раньше были #define)
  int bufsize = 100;
  char *ip = NULL;
  int port = 0;

  // === Парсинг аргументов командной строки ===
  while (1) {
    static struct option options[] = {
        {"ip",      required_argument, 0, 'i'},
        {"port",    required_argument, 0, 'p'},
        {"bufsize", required_argument, 0, 'b'},
        {0, 0, 0, 0}};
    int c = getopt_long(argc, argv, "i:p:b:", options, NULL);
    if (c == -1) break;
    switch (c) {
      case 'i': ip = optarg; break;
      case 'p': port = atoi(optarg); break;
      case 'b': bufsize = atoi(optarg); break;
    }
  }

  if (ip == NULL || port == 0) {
    printf("Usage: %s --ip <IP> --port <port> [--bufsize N]\n", argv[0]);
    exit(1);
  }

  int fd;
  int nread;
  char *buf = malloc(bufsize);   // размер буфера теперь задаётся из аргументов
  struct sockaddr_in servaddr;

  // === Создание TCP-сокета ===
  if ((fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
    perror("socket creating");
    exit(1);
  }

  memset(&servaddr, 0, SIZE);
  servaddr.sin_family = AF_INET;

  if (inet_pton(AF_INET, ip, &servaddr.sin_addr) <= 0) {
    perror("bad address");
    exit(1);
  }
  servaddr.sin_port = htons(port);

  // === Подключение к серверу ===
  if (connect(fd, (SADDR *)&servaddr, SIZE) < 0) {
    perror("connect");
    exit(1);
  }

  write(1, "Input message to send\n", 22);
  // Читаем stdin и отправляем всё серверу, пока не закончится ввод
  while ((nread = read(0, buf, bufsize)) > 0) {
    if (write(fd, buf, nread) < 0) {
      perror("write");
      exit(1);
    }
  }

  close(fd);
  free(buf);
  exit(0);
}
