#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <getopt.h>

#define SADDR struct sockaddr
#define SLEN sizeof(struct sockaddr_in)

int main(int argc, char **argv) {
  // Значения по умолчанию
  int serv_port = 20001;
  int bufsize = 1024;

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

  int sockfd, n;
  char *mesg = malloc(bufsize + 1);   // буфер для приёма
  char ipadr[16];
  struct sockaddr_in servaddr;
  struct sockaddr_in cliaddr;

  // === Создание UDP-сокета (SOCK_DGRAM) ===
  if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
    perror("socket problem");
    exit(1);
  }

  memset(&servaddr, 0, SLEN);
  servaddr.sin_family = AF_INET;
  servaddr.sin_addr.s_addr = htonl(INADDR_ANY);  // любой интерфейс
  servaddr.sin_port = htons(serv_port);

  // === Привязка к порту ===
  if (bind(sockfd, (SADDR *)&servaddr, SLEN) < 0) {
    perror("bind problem");
    exit(1);
  }

  printf("UDP server starts at port %d (bufsize=%d)...\n", serv_port, bufsize);

  // === Основной цикл: принимаем датаграммы и отправляем их обратно (эхо) ===
  while (1) {
    unsigned int len = SLEN;

    // recvfrom получает датаграмму и адрес отправителя
    if ((n = recvfrom(sockfd, mesg, bufsize, 0, (SADDR *)&cliaddr, &len)) < 0) {
      perror("recvfrom");
      exit(1);
    }
    mesg[n] = 0;   // завершаем строку

    printf("REQUEST %s      FROM %s : %d\n", mesg,
           inet_ntop(AF_INET, (void *)&cliaddr.sin_addr.s_addr, ipadr, 16),
           ntohs(cliaddr.sin_port));

    // Отправляем ту же датаграмму обратно отправителю
    if (sendto(sockfd, mesg, n, 0, (SADDR *)&cliaddr, len) < 0) {
      perror("sendto");
      exit(1);
    }
  }

  free(mesg);
}
