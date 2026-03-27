import numpy as np

class Node:
    def __init__(self, x=None, y=None, left=None, right=None, thr=None, val=None):
        self.x = x
        self.y = y
        self.left = left
        self.right = right
        self.thr = thr
        self.val = val


def mse(y):
    if len(y) == 0:
        return 0
    m = sum(y) / len(y)
    s = 0
    for v in y:
        s += (v - m) * (v - m)
    return s / len(y)


def split_try(x, y):
    best_t = None
    best_s = 10**18

    for i in range(len(x)):
        t = x[i]

        l_y = []
        r_y = []

        j = 0
        while j < len(x):
            if x[j] <= t:
                l_y.append(y[j])
            else:
                r_y.append(y[j])
            j += 1

        s = mse(l_y) * len(l_y) + mse(r_y) * len(r_y)

        if s < best_s:
            best_s = s
            best_t = t

    return best_t


def build(x, y, depth=0, max_d=5):
    if len(x) == 0:
        return None

    if depth >= max_d or len(set(y)) == 1:
        return Node(val=sum(y)/len(y))

    t = split_try(x, y)

    lx, ly, rx, ry = [], [], [], []

    i = 0
    while i < len(x):
        if x[i] <= t:
            lx.append(x[i])
            ly.append(y[i])
        else:
            rx.append(x[i])
            ry.append(y[i])
        i += 1

    node = Node(thr=t)

    node.left = build(lx, ly, depth+1, max_d)
    node.right = build(rx, ry, depth+1, max_d)

    return node


def predict_one(node, v):
    cur = node
    while True:
        if cur.val is not None:
            return cur.val
        if v <= cur.thr:
            cur = cur.left
        else:
            cur = cur.right


def predict(node, xs):
    out = []
    for v in xs:
        out.append(predict_one(node, v))
    return out


if __name__ == "__main__":
    n = int(input())
    xs = list(map(float, input().split()))
    ys = list(map(float, input().split()))

    tree = build(xs, ys, 0, 5)

    q = int(input())
    qx = list(map(float, input().split()))

    res = predict(tree, qx)

    for r in res:
        print(r)