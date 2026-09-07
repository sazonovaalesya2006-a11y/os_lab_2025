
#include <errno.h>
#include <ctype.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>

#include <getopt.h>

#include "find_min_max.h"
#include "utils.h"

// Глобальная переменная для хранения PID'ов дочерних процессов
pid_t child_pids[64]; // Максимум 64 процесса (можно увеличить)
int child_count = 0;

// Обработчик сигнала SIGALRM
void alarm_handler(int sig) {
    // Если сработал таймер, убиваем всех дочерних процессов
    printf("\nTimeout reached! Killing all child processes...\n");
    for (int i = 0; i < child_count; i++) {
        kill(child_pids[i], SIGKILL);
    }
}

int main(int argc, char **argv) {
  int seed = -1;
  int array_size = -1;
  int pnum = -1;
  bool with_files = false;
  int timeout = -1; // Новый параметр для таймаута

  // --- Парсинг аргументов командной строки с помощью getopt_long ---
  while (true) {
    int current_optind = optind ? optind : 1;

    static struct option options[] = {
        {"seed", required_argument, 0, 0},
        {"array_size", required_argument, 0, 0},
        {"pnum", required_argument, 0, 0},
        {"by_files", no_argument, 0, 'f'},
        {"timeout", required_argument, 0, 't'}, // Добавляем параметр timeout
        {0, 0, 0, 0}};

    int option_index = 0;
    int c = getopt_long(argc, argv, "ft:", options, &option_index);

    if (c == -1) break; // Конец опций

    switch (c) {
      case 0:
        switch (option_index) {
          case 0:
            seed = atoi(optarg);
            break;
          case 1:
            array_size = atoi(optarg);
            break;
          case 2:
            pnum = atoi(optarg);
            break;
          case 3:
            with_files = true;
            break;
          case 4:
            timeout = atoi(optarg); // Считываем таймаут
            break;
          default:
            printf("Index %d is out of options\n", option_index);
        }
        break;
      case 'f':
        with_files = true;
        break;
      case 't': // Если таймаут передан коротким флагом -t
        timeout = atoi(optarg);
        break;
      case '?':
        break;
      default:
        printf("getopt returned character code 0%o?\n", c);
    }
  }

  // --- Проверка корректности входных данных ---
  if (optind < argc) {
    printf("Has at least one no option argument\n");
    return 1;
  }

  if (seed == -1 || array_size == -1 || pnum == -1) {
    printf("Usage: %s --seed \"num\" --array_size \"num\" --pnum \"num\" [--timeout \"sec\"]\n",
           argv[0]);
    return 1;
  }

  // --- Выделение памяти под массив и его генерация ---
  int *array = malloc(sizeof(int) * array_size);
  GenerateArray(array, array_size, seed);
  int active_child_processes = 0;

  // --- Засекаем время начала работы программы ---
  struct timeval start_time;
  gettimeofday(&start_time, NULL);

  // --- Создание массивов пайпов (каналов) ---
  int pipes[pnum][2];
  if (!with_files) {
    for (int i = 0; i < pnum; i++) {
      if (pipe(pipes[i]) == -1) {
        printf("Pipe creation failed!\n");
        return 1;
      }
    }
  }

  // --- Устанавливаем обработчик сигнала alarm ---
  if (timeout > 0) {
    signal(SIGALRM, alarm_handler);
  }

  // --- Создание дочерних процессов ---
  for (int i = 0; i < pnum; i++) {
    pid_t child_pid = fork(); // Системный вызов fork создает новый процесс

    if (child_pid >= 0) {
      // Успешное создание процесса
      child_pids[child_count] = child_pid; // Запоминаем PID
      child_count++;
      active_child_processes += 1;

      if (child_pid == 0) {
        // === КОД ДОЧЕРНЕГО ПРОЦЕССА ===
        // Закрываем все пайпы, которые не нужны этому ребенку (кроме своего)
        if (!with_files) {
          for (int j = 0; j < pnum; j++) {
            if (j != i) {
              close(pipes[j][0]);
              close(pipes[j][1]);
            }
          }
        }

        // 1. Вычисляем границы массива для текущего процесса i
        int chunk_size = array_size / pnum;
        int remainder = array_size % pnum;
        int begin = i * chunk_size;
        int end = begin + chunk_size;
        if (i == pnum - 1) {
          end += remainder; // Последний процесс забирает остаток от деления
        }

        // 2. Каждый процесс ищет локальные мин и макс в своей части
        struct MinMax local_min_max = GetMinMax(array, begin, end);

        // 3. Передаем результат родительскому процессу
        if (with_files) {
          // Режим by_files: записываем результат в отдельный временный файл
          char filename[32];
          sprintf(filename, "temp_%d.txt", i);
          FILE *f = fopen(filename, "w");
          if (f == NULL) {
            printf("Cannot open file for writing!\n");
            return 1;
          }
          fprintf(f, "%d %d\n", local_min_max.min, local_min_max.max);
          fclose(f);
        } else {
          // Режим pipe: записываем структуру с результатом в пайп
          close(pipes[i][0]); // Закрываем конец для чтения (дочернему процессу он не нужен)
          write(pipes[i][1], &local_min_max, sizeof(struct MinMax));
          close(pipes[i][1]); // Закрываем конец для записи после отправки
        }

        return 0; // Дочерний процесс завершает работу
      }

    } else {
      // Ошибка при создании процесса
      printf("Fork failed!\n");
      return 1;
    }
  }

  // --- Если задан таймаут, запускаем таймер ---
  if (timeout > 0) {
    alarm(timeout); // Через timeout секунд будет отправлен SIGALRM
  }

  // --- Ожидание завершения всех дочерних процессов ---
  while (active_child_processes > 0) {
    // Используем waitpid с WNOHANG, чтобы не блокироваться, если дети еще работают
    int status;
    pid_t pid = waitpid(-1, &status, WNOHANG);

    if (pid > 0) {
      // Какой-то процесс завершился
      active_child_processes -= 1;
    } else if (pid == 0) {
      // Никто не завершился, просто ждем немного (1 секунда)
      sleep(1);
    } else {
      // Ошибка waitpid (например, EINTR из-за сигнала)
      if (errno == EINTR) {
        continue; // Прерывание от сигнала, продолжаем ждать
      } else {
        printf("Waitpid failed!\n");
        return 1;
      }
    }
  }

  // --- Инициализация глобальных минимального и максимального значений ---
  struct MinMax min_max;
  min_max.min = INT_MAX;
  min_max.max = INT_MIN;

  // --- Сбор и агрегация результатов от всех процессов ---
  for (int i = 0; i < pnum; i++) {
    int min = INT_MAX;
    int max = INT_MIN;

    if (with_files) {
      // Чтение результата из временного файла
      char filename[32];
      sprintf(filename, "temp_%d.txt", i);
      FILE *f = fopen(filename, "r");
      if (f == NULL) {
        printf("Cannot open file for reading!\n");
        return 1;
      }
      fscanf(f, "%d %d", &min, &max);
      fclose(f);
      remove(filename); // Удаляем временный файл после чтения
    } else {
      // Чтение результата из пайпа
      struct MinMax child_result;
      close(pipes[i][1]); // Закрываем конец для записи (родитель не пишет)
      read(pipes[i][0], &child_result, sizeof(struct MinMax));
      close(pipes[i][0]); // Закрываем конец для чтения
      min = child_result.min;
      max = child_result.max;
    }

    // Обновляем глобальные мин и макс
    if (min < min_max.min) min_max.min = min;
    if (max > min_max.max) min_max.max = max;
  }

  // --- Засекаем время окончания работы ---
  struct timeval finish_time;
  gettimeofday(&finish_time, NULL);

  // Вычисляем затраченное время в миллисекундах
  double elapsed_time = (finish_time.tv_sec - start_time.tv_sec) * 1000.0;
  elapsed_time += (finish_time.tv_usec - start_time.tv_usec) / 1000.0;

  // --- Освобождение памяти ---
  free(array);

  // --- Вывод результатов ---
  printf("Min: %d\n", min_max.min);
  printf("Max: %d\n", min_max.max);
  printf("Elapsed time: %fms\n", elapsed_time);
  fflush(NULL);
  return 0;
}