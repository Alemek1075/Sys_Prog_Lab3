#include <iostream>
using namespace std;

int gcd(int a, int b) {
    while (b != 0) {
        int r = a % b;
        a = b;
        b = r;
    }
    return a;
}

double mySqrt(double x) {
    double g = x / 2;
    int steps = 0;
    do {
        g = (g + x / g) / 2;
        steps++;
    } while (steps < 20);
    return g;
}

int main() {
    cout << "gcd(84, 36) = " << gcd(84, 36) << endl;
    cout << "sqrt(2) = " << mySqrt(2) << endl;
    cout << "7 / 2 = " << 7 / 2 << ", 7.0 / 2 = " << 7.0 / 2 << endl;
    cout << "-7 / 2 = " << -7 / 2 << ", -7 % 2 = " << -7 % 2 << endl;
    int x = 5;
    int y = x++;
    int z = ++x;
    cout << "x = " << x << ", y = " << y << ", z = " << z << endl;
    cout << (x > 3 && y < 100) << " " << (x > 10 ? 1 : 0) << endl;
    return 0;
}
