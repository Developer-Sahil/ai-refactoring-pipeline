import imageio.v2 as imageio
import numpy as np

def root_mean_square_error(a, b):
    return float(np.sqrt(((a - b) ** 2).mean()))

def normalize_image(img, cap=255.0, dt=np.uint8):
    mn = np.min(img)
    mx = np.max(img)
    norm = (img - mn) / (mx - mn) * cap
    return norm.astype(dt)

def normalize_array(arr, cap=1):
    mn = np.min(arr)
    mx = np.max(arr)
    d = mx - mn
    if d == 0:
        d = 1
    return (arr - mn) / d * cap

def grayscale(img):
    return np.dot(img[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)

def binarize(img, th=127.0):
    return np.where(img > th, 1, 0)

def transform(img, kind, kernel=None):
    if kernel is None:
        kernel = np.ones((3, 3))

    if kind == "erosion":
        c = 1
        fn = np.max
    else:
        c = 0
        fn = np.min

    cx = kernel.shape[0] // 2
    cy = kernel.shape[1] // 2

    out = np.zeros(img.shape, dtype=np.uint8)
    pad = np.pad(img, 1, mode="constant", constant_values=c)

    for i in range(cx, pad.shape[0] - cx):
        for j in range(cy, pad.shape[1] - cy):
            sub = pad[i-cx:i+cx+1, j-cy:j+cy+1]
            val = fn(sub[kernel == 1])
            out[i-cx, j-cy] = val

    return out

def opening_filter(img, kernel=None):
    if kernel is None:
        np.ones((3, 3))
    return transform(transform(img, "dilation", kernel), "erosion", kernel)

def closing_filter(img, kernel=None):
    if kernel is None:
        kernel = np.ones((3, 3))
    return transform(transform(img, "erosion", kernel), "dilation", kernel)

def binary_mask(gray, mp):
    t = gray.copy()
    f = gray.copy()
    t[mp == 1] = 1
    f[mp == 0] = 0
    return t, f

def matrix_concurrency(img, coord):
    m = np.zeros([np.max(img)+1, np.max(img)+1])
    ox, oy = coord

    for i in range(1, img.shape[0]-1):
        for j in range(1, img.shape[1]-1):
            b = img[i, j]
            o = img[i+ox, j+oy]
            m[b, o] += 1

    s = np.sum(m)
    if s == 0:
        s = 1
    return m / s

def haralick_descriptors(m):
    i, j = np.ogrid[0:m.shape[0], 0:m.shape[1]]

    prod = i * j
    sub = i - j

    maxp = np.max(m)
    corr = prod * m
    energy = m ** 2
    contrast = m * (sub ** 2)

    dis = m * np.abs(sub)
    inv = m / (1 + np.abs(sub))
    homo = m / (1 + (sub ** 2))

    ent = -(m[m > 0] * np.log(m[m > 0]))

    return [
        maxp,
        corr.sum(),
        energy.sum(),
        contrast.sum(),
        dis.sum(),
        inv.sum(),
        homo.sum(),
        ent.sum()
    ]

def get_descriptors(masks, coord):
    arr = []
    for m in masks:
        arr.append(haralick_descriptors(matrix_concurrency(m, coord)))
    arr = np.array(arr)
    return np.concatenate(arr, axis=None)

def euclidean(a, b):
    return float(np.sqrt(np.sum((a - b) ** 2)))

def get_distances(desc, base):
    d = []
    for x in desc:
        d.append(euclidean(x, desc[base]))

    d = np.array(d)
    d = normalize_array(d, 1).tolist()

    e = list(enumerate(d))
    e.sort(key=lambda x: x[1], reverse=True)
    return e

if __name__ == "__main__":
    idx = int(input())
    qv = input().split()
    qv = (int(qv[0]), int(qv[1]))

    params = {"format": int(input()), "threshold": int(input())}

    n = int(input())

    files = []
    descs = []

    for _ in range(n):
        f = input().strip()
        files.append(f)

        img = imageio.imread(f).astype(np.float32)
        g = grayscale(img)
        th = binarize(g, params["threshold"])

        if params["format"] == 1:
            morph = opening_filter(th)
        else:
            morph = closing_filter(th)

        masks = binary_mask(g, morph)
        descs.append(get_descriptors(masks, qv))

    dist = get_distances(np.array(descs), idx)
    order = np.array(dist).astype(np.uint8)[:, 0]

    print(f"Query: {files[idx]}")
    print("Ranking:")
    for i, fi in enumerate(order):
        print(f"({i}) {files[fi]}")