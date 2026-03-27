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

import numpy as np

def haralick_descriptors(m):
    """
    Calculate Haralick texture descriptors from a gray-level co-occurrence matrix (GLCM).

    This function computes eight common Haralick texture features from an input
    matrix, typically a GLCM, which quantifies the frequency of pixel pairs
    with specific values and spatial relationships. The calculations are based
    on the spatial distribution and values within the matrix.

    Args:
        m (np.ndarray): The input 2D matrix (e.g., a normalized GLCM) from which
                        to calculate the Haralick descriptors.
                        It is expected to be a matrix of non-negative values.

    Returns:
        list: A list containing the eight Haralick texture descriptors in the
              following order:
              1. Maximum Probability (max_p)
              2. Correlation (corr)
              3. Energy (ASM - Angular Second Moment)
              4. Contrast
              5. Dissimilarity
              6. Inverse Difference Moment (IDM)
              7. Homogeneity
              8. Entropy
    """
    # Create 2D arrays of row and column indices for element-wise operations
    row_indices, col_indices = np.ogrid[0:m.shape[0], 0:m.shape[1]]

    # Calculate intermediate index-based terms
    product_of_indices = row_indices * col_indices
    difference_of_indices = row_indices - col_indices

    # 1. Maximum Probability (max_p)
    maximum_value = np.max(m)

    # 2. Correlation
    # This is a simplified form of correlation often used directly with the GLCM cell values.
    # The full GLCM correlation formula involves means and standard deviations of marginal probabilities,
    # but this implementation directly uses the product of indices weighted by the matrix values.
    correlation_term = product_of_indices * m
    correlation_descriptor = correlation_term.sum()

    # 3. Energy (Angular Second Moment - ASM)
    energy_term = m ** 2
    energy_descriptor = energy_term.sum()

    # 4. Contrast
    contrast_term = m * (difference_of_indices ** 2)
    contrast_descriptor = contrast_term.sum()

    # 5. Dissimilarity
    dissimilarity_term = m * np.abs(difference_of_indices)
    dissimilarity_descriptor = dissimilarity_term.sum()

    # 6. Inverse Difference Moment (IDM)
    inverse_difference_moment_term = m / (1 + np.abs(difference_of_indices))
    inverse_difference_moment_descriptor = inverse_difference_moment_term.sum()

    # 7. Homogeneity
    homogeneity_term = m / (1 + (difference_of_indices ** 2))
    homogeneity_descriptor = homogeneity_term.sum()

    # 8. Entropy
    # Only consider positive matrix elements for log calculation to avoid issues with log(0)
    positive_matrix_elements = m[m > 0]
    entropy_terms = -(positive_matrix_elements * np.log(positive_matrix_elements))
    entropy_descriptor = entropy_terms.sum()

    return [
        maximum_value,
        correlation_descriptor,
        energy_descriptor,
        contrast_descriptor,
        dissimilarity_descriptor,
        inverse_difference_moment_descriptor,
        homogeneity_descriptor,
        entropy_descriptor
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