#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    printf("[Lapis Core Engine v1.0.0]\n");
    if (argc > 1) {
        printf("Executing Lapis file: %s\n", argv[1]);
    } else {
        printf("Usage: lapis <file.lp>\n");
    }
    return 0;
}