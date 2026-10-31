#include <iostream>
using namespace std;

bool isPrime(int n) {
    if (n < 2) return false;
    for (int d = 2; d * d <= n; d++)
        if (n % d == 0) return false;
    return true;
}

int main() {
    int count = 0, limit = 50;
    for (int i = 0; i <= limit; i++) {
        if (!isPrime(i)) continue;
        cout << i << " ";
        count++;
    }
    cout << endl << "primes up to " << limit << ": " << count << endl;
    return 0;
}
