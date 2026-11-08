#include <stdio.h>
#include <limits.h>
int main() {
    int x = INT_MAX;
    if (x + 1 < x) printf("wrapped\n"); else printf("no wrap\n");
    return 0;
}
