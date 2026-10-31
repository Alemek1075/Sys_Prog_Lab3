#include <iostream>
using namespace std;

int main() {
    int a = 1, b = 0;
    if (a)
        if (b)
            cout << "a and b" << endl;
        else
            cout << "a, not b" << endl;
    return 0;
}
