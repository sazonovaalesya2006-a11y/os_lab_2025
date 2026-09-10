#ifndef COMMON_H
#define COMMON_H

#include <stdbool.h>
#include <stdint.h>

// Умножение по модулю без переполнения (a * b mod mod).
// Используется и клиентом, и сервером.
uint64_t MultModulo(uint64_t a, uint64_t b, uint64_t mod);

// Преобразование строки в uint64_t с проверкой ошибок.
// Используется клиентом для парсинга аргументов.
bool ConvertStringToUI64(const char *str, uint64_t *val);

#endif
