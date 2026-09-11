#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <arpa/inet.h>
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
  char *ip = NULL;

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
      case 'p': serv_port = atoi(optarg); break;
      case 'b': bufsize = atoi(optarg); break;
    }
  }

  if (ip == NULL) {
    printf("Usage: %s --ip <IP> [--port N] [--bufsize N]\n", argv[0]);
    exit(1);
  }

  int sockfd, n;
  char *sendline = malloc(bufsize);          // буфер отправки
  char *recvline = malloc(bufsize + 1);      // буфер приёма (+1 для '\0')
  struct sockaddr_in servaddr;

  memset(&servaddr, 0, sizeof(servaddr));
  servaddr.sin_family = AF_INET;
  servaddr.sin_port = htons(serv_port);

  if (inet_pton(AF_INET, ip, &servaddr.sin_addr) < 0) {
    perror("inet_pton problem");
    exit(1);
  }

  // === Создание UDP-сокета (SOCK_DGRAM) ===
  if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
    perror("socket problem");
    exit(1);
  }

  write(1, "Enter string\n", 13);

  // Читаем строки со stdin, отправляем серверу, получаем ответ
  while ((n = read(0, sendline, bufsize)) > 0) {
    if (sendto(sockfd, sendline, n, 0, (SADDR *)&servaddr, SLEN) == -1) {
      perror("sendto problem");
      exit(1);
    }

    if (recvfrom(sockfd, recvline, bufsize, 0, NULL, NULL) == -1) {
      perror("recvfrom problem");
      exit(1);
    }

    recvline[n] = '\0';   // завершаем строку
    printf("REPLY FROM SERVER= %s\n", recvline);
  }

  close(sockfd);
  free(sendline);
  free(recvline);
}
