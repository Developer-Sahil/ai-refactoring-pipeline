import imageio.v2 as imageio
import numpy as np

def root_mean_square_error(a: np.ndarray, b: np.ndarray) -> float:
    """
    Calculates the Root Mean Square Error (RMSE) between two NumPy arrays.

    Args:
        a: The first input array.
        b: The second input array.

    Returns:
        The RMSE as a float.
    """
    return float(np.sqrt(np.mean((a - b) ** 2)))

def normalize_image(img: np.ndarray, cap: float = 255.0, dtype: type = np.uint8) -> np.ndarray:
    """
    Normalizes an image array to a specified range and data type.

    Scales the pixel values of the input image to be within [0, `cap`]
    and then casts it to the specified data type. Handles cases where
    the image is uniform (all pixels have the same value) to prevent
    division by zero.

    Args:
        img:   The input image as a NumPy array.
        cap:   The maximum value for the normalized image (default is 255.0).
        dtype: The desired data type for the output image (default is np.uint8).

    Returns:
        The normalized image as a NumPy array with the specified data type.
    """
    min_val = np.min(img)
    max_val = np.max(img)

    # Handle the case where the image is uniform (all pixels have the same value)
    if min_val == max_val:
        return np.zeros_like(img, dtype=dtype)

    normalized_img = (img - min_val) / (max_val - min_val) * cap
    return normalized_img.astype(dtype)

def normalize_array(arr: np.ndarray, cap: Union[int, float] = 1) -> np.ndarray:
    """
    Normalizes a NumPy array to a specified maximum value.

    Scales the array values to be within the range [0, `cap`].
    If all elements in the array are identical, the function
    returns an array of zeros.

    Args:
        arr: The input NumPy array to normalize.
        cap: The maximum value for the normalized array (default is 1).

    Returns:
        The normalized NumPy array.
    """
    min_val = np.min(arr)
    max_val = np.max(arr)

    # Calculate the range
    data_range = max_val - min_val

    # Handle division by zero if all array elements are identical
    if data_range == 0:
        data_range = 1 # This results in (arr - min_val) / 1 * cap, which simplifies to 0 * cap = 0 if uniform.

    normalized_arr = (arr - min_val) / data_range * cap
    return normalized_arr

import numpy as np

def grayscale(img: np.ndarray) -> np.ndarray:
    """
    Converts a color image (RGB or RGBA) to a grayscale image.

    Applies the ITU-R BT.601 luminosity method: Y = 0.299*R + 0.587*G + 0.114*B.

    Args:
        img: The input color image as a NumPy array (H, W, C), where C >= 3.

    Returns:
        A grayscale image as a NumPy array with dtype np.uint8.
    """
    # Use only the first three channels (R, G, B) if more channels exist (e.g., RGBA)
    # Perform dot product for weighted sum and cast to unsigned 8-bit integer.
    RGB_TO_GRAY_WEIGHTS = [0.299, 0.587, 0.114]
    return np.dot(img[:, :, :3], RGB_TO_GRAY_WEIGHTS).astype(np.uint8)

import numpy as np

def binarize(img: np.ndarray, threshold: float = 127.0) -> np.ndarray:
    """
    Binarizes a grayscale image based on a given threshold.

    Pixels with values strictly greater than the threshold become 1, otherwise 0.

    Args:
        img:       The input grayscale image as a NumPy array.
        threshold: The threshold value. Defaults to 127.0.

    Returns:
        A binary image as a NumPy array (containing 0s and 1s).
    """
    # Using np.where to assign 1 or 0 based on the comparison
    return np.where(img > threshold, 1, 0)

import numpy as np
from typing import Literal, Optional

def transform(
    img: np.ndarray,
    kind: Literal["erosion", "dilation"],
    kernel: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Performs a morphological erosion or dilation operation on a binary image.

    This function implements a basic 2D morphological transformation using a
    manual sliding window approach. It's intended for binary images where
    the foreground is typically 1 and background is 0 (for erosion)
    or vice versa (for dilation).

    Args:
        img:    The input binary image as a NumPy array (typically uint8, 0s and 1s).
        kind:   The type of morphological operation to perform: "erosion" or "dilation".
        kernel: The structuring element (kernel) as a NumPy array. Should contain 0s
                and 1s, where 1s define the shape of the structuring element.
                If None, a default 3x3 square kernel of ones is used.

    Returns:
        The transformed image as a NumPy array with dtype np.uint8.

    Raises:
        ValueError: If an unsupported 'kind' of transformation is requested.
    """
    if kernel is None:
        kernel = np.ones((3, 3), dtype=np.uint8)

    # Determine padding value and aggregation function based on the operation kind
    if kind == "erosion":
        # For erosion, border pixels should be considered foreground (1)
        # The operation func takes the minimum over the kernel area
        border_value = 1
        operation_func = np.min
    elif kind == "dilation":
        # For dilation, border pixels should be considered background (0)
        # The operation func takes the maximum over the kernel area
        border_value = 0
        operation_func = np.max
    else:
        raise ValueError(f"Unsupported transformation kind: {kind}. Expected 'erosion' or 'dilation'.")

    # Calculate center offsets of the kernel for proper padding
    center_x = kernel.shape[0] // 2
    center_y = kernel.shape[1] // 2

    output_image = np.zeros(img.shape, dtype=np.uint8)

    # Pad the image based on kernel dimensions to handle border pixels correctly
    # Padding with (center_x, center_x) on axis 0 and (center_y, center_y) on axis 1
    padded_image = np.pad(
        img,
        ((center_x, center_x), (center_y, center_y)),
        mode="constant",
        constant_values=border_value
    )

    # Iterate over the dimensions of the original image to compute each output pixel
    for r in range(img.shape[0]):
        for c in range(img.shape[1]):
            # Extract the sub-region from the padded image.
            # The sub-region's top-left corner (r, c) in the padded image corresponds
            # to the (r, c) pixel in the output image, making the kernel centered.
            sub_region = padded_image[
                r : r + kernel.shape[0],
                c : c + kernel.shape[1]
            ]
            
            # Apply the morphological operation function (min for erosion, max for dilation)
            # only to the pixels covered by the kernel's '1's.
            value = operation_func(sub_region[kernel == 1])
            output_image[r, c] = value

    return output_image

def opening_filter(img: np.ndarray, kernel: np.ndarray | None = None) -> np.ndarray:
    """
    Applies an opening morphological filter to a binary image.

    Opening is defined as an erosion followed by a dilation.
    It can remove small objects and smooth object boundaries.

    Args:
        img:    The input binary image (numpy array, typically 0s and 1s).
        kernel: The structuring element used for erosion and dilation.
                If None, a 3x3 square kernel of ones is used.

    Returns:
        The image after applying the opening filter.
    """
    if kernel is None:
        kernel = np.ones((3, 3))
    dilated_img = transform(img, "dilation", kernel)
    eroded_dilated_img = transform(dilated_img, "erosion", kernel)
    return eroded_dilated_img

def closing_filter(img: np.ndarray, kernel: np.ndarray | None = None) -> np.ndarray:
    """
    Applies a closing morphological filter to a binary image.

    Closing is defined as a dilation followed by an erosion.
    It can fill small holes, connect nearby objects, and smooth object boundaries.

    Args:
        img:    The input binary image (numpy array, typically 0s and 1s).
        kernel: The structuring element used for erosion and dilation.
                If None, a 3x3 square kernel of ones is used.

    Returns:
        The image after applying the closing filter.
    """
    if kernel is None:
        kernel = np.ones((3, 3))
    eroded_img = transform(img, "erosion", kernel)
    dilated_eroded_img = transform(eroded_img, "dilation", kernel)
    return dilated_eroded_img

def binary_mask(gray: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Applies a binary mask to a grayscale image in two different ways.

    Args:
        gray: The input grayscale image (numpy array, e.g., np.uint8 with 0-255 values).
        mask: The binary mask (numpy array, typically 0s and 1s),
              where 1 indicates the foreground and 0 the background.

    Returns:
        A tuple containing two masked images:
        - `foreground_as_one_image`: A copy of `gray` where pixels corresponding
          to `mask == 1` are set to 1, and other pixels retain their `gray` value.
        - `masked_foreground_image`: A copy of `gray` where pixels corresponding
          to `mask == 0` are set to 0, and other pixels retain their `gray` value.
    """
    foreground_as_one_image = gray.copy()
    masked_foreground_image = gray.copy()

    # Set foreground pixels to 1 in the first output
    foreground_as_one_image[mask == 1] = 1
    # Set background pixels to 0 in the second output
    masked_foreground_image[mask == 0] = 0

    return foreground_as_one_image, masked_foreground_image

def matrix_concurrency(img: np.ndarray, coord: tuple[int, int]) -> np.ndarray:
    """
    Calculates the Gray-Level Co-occurrence Matrix (GLCM) for a given image.

    The GLCM is a matrix where each element (i, j) represents the number of times
    pixel value i occurs with pixel value j at a specified offset. This matrix
    is then normalized by the total number of co-occurrences to give probabilities.

    Args:
        img:   Input image (2D numpy array), expected to contain non-negative integer pixel values.
               Values should be in the range [0, P-1] where P is the number of gray levels.
        coord: A tuple (ox, oy) specifying the offset vector.
               (ox, oy) represents the displacement from the current pixel (row, col)
               to the neighboring pixel (row + ox, col + oy).

    Returns:
        The GLCM (2D numpy array), normalized by the total number of co-occurrences.
        Returns a zero matrix (of float type) if no co-occurrences are found or
        if the image is empty.
    """
    if img.ndim != 2:
        raise ValueError("Input image must be a 2D array.")
    if img.size == 0:
        # Return a small zero matrix of float type if the image is empty
        return np.zeros((1, 1), dtype=np.float64)

    max_pixel_val = int(np.max(img))
    
    # Initialize GLCM with dimensions (max_pixel_val + 1) x (max_pixel_val + 1)
    # Use int32 for counts to prevent overflow for large images before normalization.
    glcm = np.zeros([max_pixel_val + 1, max_pixel_val + 1], dtype=np.int32)

    offset_x, offset_y = coord
    num_rows, num_cols = img.shape

    # Define iteration ranges such that both (r, c) and (r + offset_x, c + offset_y)
    # are within the image boundaries.
    row_start = max(0, -offset_x)
    row_end = num_rows - max(0, offset_x)
    col_start = max(0, -offset_y)
    col_end = num_cols - max(0, offset_y)

    for r in range(row_start, row_end):
        for c in range(col_start, col_end):
            current_pixel_val = img[r, c]
            offset_pixel_val = img[r + offset_x, c + offset_y]
            glcm[current_pixel_val, offset_pixel_val] += 1

    total_occurrences = np.sum(glcm)
    if total_occurrences == 0:
        # Avoid division by zero, return a zero matrix (float) if no co-occurrences.
        return glcm.astype(np.float64)
    else:
        return glcm / total_occurrences

def haralick_descriptors(glcm: np.ndarray) -> list[float]:
    """
    Calculates a set of Haralick texture descriptors from a Gray-Level Co-occurrence Matrix (GLCM).

    Args:
        glcm: The normalized GLCM (2D numpy array) where glcm[i,j] is the probability
              of co-occurrence of pixel values i and j.

    Returns:
        A list of float values representing the calculated Haralick descriptors:
        [
            Maximum Probability,
            Correlation (normalized),
            Angular Second Moment (Energy),
            Contrast,
            Dissimilarity,
            Inverse Difference Moment (Homogeneity 1),
            Homogeneity (Homogeneity 2),
            Entropy
        ]
        Returns a list of zeros if the GLCM is empty or all zeros.
    """
    num_levels = glcm.shape[0]

    # Handle cases where GLCM is all zeros (e.g., from an empty image or no co-occurrences).
    # All descriptors would become 0 or NaN.
    if np.sum(glcm) == 0:
        return [0.0] * 8 # Return a list of zeros for consistency

    i_indices, j_indices = np.ogrid[0:num_levels, 0:num_levels]

    # 1. Maximum Probability
    max_probability = np.max(glcm)

    # 2. Correlation (normalized)
    # Calculate marginal probability distributions
    px = np.sum(glcm, axis=1)
    py = np.sum(glcm, axis=0)

    # Calculate means of i and j
    mean_x = np.sum(i_indices[:, 0] * px)
    mean_y = np.sum(j_indices[0, :] * py)

    # Calculate standard deviations of i and j
    variance_x = np.sum((i_indices[:, 0] - mean_x)**2 * px)
    variance_y = np.sum((j_indices[0, :] - mean_y)**2 * py)

    std_dev_x = np.sqrt(variance_x)
    std_dev_y = np.sqrt(variance_y)

    correlation = 0.0
    if std_dev_x > 0 and std_dev_y > 0:
        correlation = np.sum(glcm * (i_indices - mean_x) * (j_indices - mean_y)) / (std_dev_x * std_dev_y)

    # 3. Angular Second Moment (Energy)
    energy = np.sum(glcm ** 2)

    # 4. Contrast
    contrast = np.sum(glcm * ((i_indices - j_indices) ** 2))

    # 5. Dissimilarity
    dissimilarity = np.sum(glcm * np.abs(i_indices - j_indices))

    # 6. Inverse Difference Moment (Homogeneity 1)
    inverse_difference_moment = np.sum(glcm / (1 + np.abs(i_indices - j_indices)))

    # 7. Homogeneity (Homogeneity 2, also known as Inverse Difference Moment Normalized)
    homogeneity = np.sum(glcm / (1 + (i_indices - j_indices) ** 2))

    # 8. Entropy
    # Only consider non-zero probabilities to avoid log(0)
    non_zero_glcm_values = glcm[glcm > 0]
    entropy = -np.sum(non_zero_glcm_values * np.log(non_zero_glcm_values))

    return [
        float(max_probability),
        float(correlation),
        float(energy),
        float(contrast),
        float(dissimilarity),
        float(inverse_difference_moment),
        float(homogeneity),
        float(entropy)
    ]

def get_descriptors(masks: tuple[np.ndarray, np.ndarray], coord: tuple[int, int]) -> np.ndarray:
    """
    Calculates Haralick texture descriptors for a collection of image masks.

    This function processes each mask in the input tuple, computes its
    Gray-Level Co-occurrence Matrix (GLCM) using the given offset coordinates,
    and then extracts Haralick texture descriptors from the GLCM.
    All calculated descriptors are then concatenated into a single 1D NumPy array.

    Args:
        masks: A tuple of 2D numpy arrays (e.g., (grayscale_image, binary_mask)).
               Each array represents an image or mask for which descriptors are to be computed.
        coord: A tuple (ox, oy) specifying the offset vector for GLCM calculation.

    Returns:
        A 1D numpy array containing all Haralick descriptors concatenated
        from each processed mask. The array elements are of float type.
    """
    # Use a list comprehension to build the list of descriptor lists for each mask
    all_descriptors_for_masks = [
        haralick_descriptors(matrix_concurrency(mask, coord))
        for mask in masks
    ]
    
    # Concatenate the list of descriptor lists into a single 1D numpy array.
    # axis=None flattens the resulting array.
    if not all_descriptors_for_masks:
        return np.array([], dtype=np.float64)

    return np.concatenate(all_descriptors_for_masks, axis=None).astype(np.float64)

def euclidean(a: np.ndarray, b: np.ndarray) -> float:
    """
    Calculates the Euclidean distance between two NumPy arrays.

    Args:
        a: The first NumPy array.
        b: The second NumPy array.

    Returns:
        The Euclidean distance as a float.
    """
    return float(np.sqrt(np.sum((a - b) ** 2)))

def get_distances(descriptors: np.ndarray, base_index: int) -> list[tuple[int, float]]:
    """
    Calculates normalized Euclidean distances of all descriptors to a base descriptor,
    and returns them ranked by dissimilarity (largest distance first).

    Args:
        descriptors: A NumPy array where each row is a descriptor vector.
        base_index: The index of the descriptor in `descriptors` to use as the base
                    for distance calculation.

    Returns:
        A list of tuples, where each tuple contains (original_index, normalized_distance).
        The list is sorted in descending order of normalized distance.
    """
    base_descriptor = descriptors[base_index]
    
    # Calculate Euclidean distances for all descriptors relative to the base
    distances = [euclidean(x, base_descriptor) for x in descriptors]

    # Convert to numpy array, normalize to [0, 1], then convert back to list
    distances_array = np.array(distances)
    normalized_distances = normalize_array(distances_array, cap=1).tolist()

    # Pair original indices with their normalized distances and sort by distance
    ranked_items = list(enumerate(normalized_distances))
    ranked_items.sort(key=lambda x: x[1], reverse=True) # Sort by distance, largest first
    
    return ranked_items

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