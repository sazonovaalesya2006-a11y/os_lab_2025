#include "common.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

// Умножение по модулю без переполнения.
// Реализовано через "русское умножение" (сложение и удвоение),
// потому что прямое a*b может переполнить uint64_t.
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
