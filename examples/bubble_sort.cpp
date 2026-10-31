#include <iostream>
using namespace std;

void sort(int a[], int n) {
    for (int i = 0; i < n - 1; i++) {
        bool swapped = false;
        for (int j = 0; j < n - 1 - i; j++) {
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
                swapped = true;
            }
        }
        if (!swapped)
            break;
    }
}

int main() {
    int a[8] = {42, 7, 19, -3, 0, 88, 7, 15};
    sort(a, 8);
    for (int i = 0; i < 8; i++)
        cout << a[i] << " ";
    cout << endl;
}
