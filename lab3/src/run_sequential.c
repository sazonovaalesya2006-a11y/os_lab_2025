#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

int main(int argc, char *argv[]) {
    // Проверяем, переданы ли аргументы (seed и array_size)
    if (argc < 3) {
        printf("Usage: %s <seed> <array_size>\n", argv[0]);
        return 1;
    }

    pid_t pid = fork();

    if (pid == -1) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        // Дочерний процесс: запускаем sequential_min_max
        // argv[1] - seed, argv[2] - array_size
        // execvp заменяет текущий образ процесса на новый
        char *args[] = {"./sequential_min_max", argv[1], argv[2], NULL};
        execvp(args[0], args);

        // Если execvp вернулся, значит произошла ошибка
        perror("execvp");
        exit(1);
    } else {
        // Родительский процесс: ждем завершения дочернего
        int status;
        waitpid(pid, &status, 0);
        printf("Child process finished with status: %d\n", WEXITSTATUS(status));
    }

    return 0;
}
