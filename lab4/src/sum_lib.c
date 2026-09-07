#include "sum_lib.h"

long long calculate_sum(const int *array, size_t start, size_t end) {
    long long sum = 0;
    for (size_t i = start; i < end; ++i) {
        sum += array[i];
    }
    return sum;
}
