import sys

def solve():
    data = sys.stdin.read().strip().split()
    if not data:
        return

    it = 0
    n = int(data[it]); it += 1

    mat = []
    for _ in range(n):
        row = []
        for _ in range(n):
            row.append(int(data[it])); it += 1
        mat.append(row)

    size = 1 << n
    dp = [-1] * size

    def f(mask):
        if mask == (1 << n) - 1:
            return 0

        if dp[mask] != -1:
            return dp[mask]

        i = bin(mask).count("1")

        best = -10**18

        j = 0
        while j < n:
            if not (mask & (1 << j)):
                val = mat[i][j] + f(mask | (1 << j))
                if val > best:
                    best = val
            j += 1

        dp[mask] = best
        return best

    ans = f(0)
    sys.stdout.write(str(ans))


if __name__ == "__main__":
    solve()