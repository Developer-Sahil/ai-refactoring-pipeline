import imageio.v2 as imageio
import numpy as np

import numpy as np

def root_mean_square_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate the Root Mean Square Error (RMSE) between two arrays.

    RMSE is a commonly used metric to measure the magnitude of the average
    difference between values predicted by a model or estimator and the
    actual observed values. A lower RMSE indicates a better fit of the model
    to the data.

    Args:
        y_true: An array-like object containing the true or actual values.
        y_pred: An array-like object containing the predicted or estimated values.

    Returns:
        The Root Mean Square Error as a standard Python float.
    """
    # Calculate the element-wise squared differences
    squared_differences = (y_true - y_pred) ** 2

    # Calculate the mean of the squared differences (Mean Squared Error)
    mean_squared_error = squared_differences.mean()

    # Take the square root to get the Root Mean Square Error
    rmse_value = np.sqrt(mean_squared_error)

    # Convert the result to a standard Python float
    return float(rmse_value)

import numpy as np

def normalize_image(img, cap=255.0, dt=np.uint8):
    """
    Normalizes an image array to a specified maximum value and data type.

    The input image is linearly scaled so that its minimum value becomes 0
    and its maximum value becomes `cap`. The result is then cast to `dt`.

    Args:
        img (numpy.ndarray): The input image array.
        cap (float): The maximum value to which the normalized image will be
                     scaled. Defaults to 255.0, typical for 8-bit images.
        dt (numpy.dtype): The desired data type for the output image array.
                          Defaults to np.uint8.

    Returns:
        numpy.ndarray: The normalized image array with the specified data type.

    Raises:
        ZeroDivisionError: If the input image array contains only a single
                           unique value (i.e., `np.min(img) == np.max(img)`),
                           as division by zero would occur during scaling.
    """
    min_pixel_value = np.min(img)
    max_pixel_value = np.max(img)

    # The original code would raise a ZeroDivisionError if max_pixel_value == min_pixel_value.
    # We preserve this behavior as per the constraint: "Do NOT change the observable behaviour".
    scaled_image = (img - min_pixel_value) / (max_pixel_value - min_pixel_value) * cap

    return scaled_image.astype(dt)

import numpy as np


def normalize_array(arr: np.ndarray, cap: float = 1.0) -> np.ndarray:
    """
    Normalize a NumPy array to a target range, typically [0, cap].

    This function scales the input array `arr` such that its minimum value
    becomes 0 and its maximum value becomes `cap`. If all elements in the
    array are identical, the normalized array will consist entirely of zeros.

    Args:
        arr: The input NumPy array to be normalized.
        cap: The desired maximum value after normalization. The minimum value
             will be 0. Defaults to 1.0.

    Returns:
        A new NumPy array with values scaled to the range [0, cap].
    """
    min_value = np.min(arr)
    max_value = np.max(arr)
    data_range = max_value - min_value

    # Prevent division by zero if all array elements are identical.
    # In this case, the data_range is 0, and the normalized array should be all zeros.
    # Setting data_range to 1.0 effectively makes (arr - min_value) / 1.0,
    # which for a constant array (where arr == min_value) results in zeros.
    EFFECTIVE_MIN_RANGE = 1.0
    if data_range == 0:
        data_range = EFFECTIVE_MIN_RANGE

    normalized_arr = (arr - min_value) / data_range * cap
    return normalized_arr

def grayscale(img):
    """
    Converts an RGB image to grayscale using the luminosity method.

    This method applies standard ITU-R BT.601 coefficients to
    the red, green, and blue channels to calculate the perceived
    brightness of each pixel.

    Args:
        img (np.ndarray): The input RGB image array. Expected shape is
                          (height, width, 3), where the last dimension
                          represents the R, G, B channels, respectively.
                          Pixel values are typically in the range [0, 255].

    Returns:
        np.ndarray: The grayscale image array. Its shape will be
                    (height, width) and its data type will be np.uint8.
                    Pixel values will range from 0 (black) to 255 (white).
    """
    # Standard ITU-R BT.601 coefficients for converting RGB to grayscale.
    # These weights approximate human perception of brightness:
    # Red (0.299), Green (0.587), Blue (0.114).
    LUMINOSITY_WEIGHTS = [0.299, 0.587, 0.114]

    # Calculate the dot product of the RGB channels with the luminosity weights.
    # img[:, :, :3] selects the R, G, B channels, ignoring any potential alpha.
    # The result is a 2D array where each element is the grayscale value.
    # Finally, convert the resulting float array to 8-bit unsigned integers (0-255).
    return np.dot(img[:, :, :3], LUMINOSITY_WEIGHTS).astype(np.uint8)

import numpy as np

def binarize(image_array: np.ndarray, threshold_value: float = 127.0) -> np.ndarray:
    """
    Binarize an input NumPy array based on a specified threshold.

    This function transforms a multi-valued array into a binary array.
    Elements strictly greater than the `threshold_value` are set to 1,
    while all other elements are set to 0.

    Args:
        image_array:     The input NumPy array (e.g., an image) to be binarized.
                         Expected to be numerical.
        threshold_value: The scalar threshold value. Elements in `image_array`
                         that are strictly greater than this value will be set to 1.
                         Defaults to 127.0.

    Returns:
        A new NumPy array of type `int` (typically `np.int_`) with the same shape
        as `image_array`, containing only 0s and 1s.
    """
    return np.where(image_array > threshold_value, 1, 0)

import numpy as np
from typing import Optional

def transform(input_image: np.ndarray, operation_type: str, structuring_element: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Apply a morphological operation to a 2D image.

    This function performs a basic morphological operation (either a max-filter
    with 1-padding or a min-filter with 0-padding) on the input image using
    a specified structuring element. If no structuring element is provided,
    a default 3x3 kernel of ones is used.

    The behavior depends on the `operation_type` string:
    - If `operation_type` is "erosion": the output pixel is the maximum value
      of the neighborhood covered by the structuring element, with the image
      padded with ones. This operation effectively dilates foreground pixels (value 1).
    - For any other `operation_type`: the output pixel is the minimum value
      of the neighborhood covered by the structuring element, with the image
      padded with zeros. This operation effectively erodes foreground pixels (value 1).

    Args:
        input_image:         The input 2D image array (e.g., a grayscale image).
                             Expected dtype is np.uint8.
        operation_type:      The string determining the type of operation.
                             Use "erosion" for the max-filter (dilation-like) operation.
                             Any other string will trigger the min-filter (erosion-like) operation.
        structuring_element: The structuring element (kernel) to use for the operation.
                             If None, a 3x3 kernel of ones is used. Only elements with
                             value 1 in the kernel contribute to the neighborhood
                             aggregation.

    Returns:
        A new NumPy array (np.uint8) representing the transformed image.
    """
    # --- Constants for improved readability and maintainability ---
    DEFAULT_KERNEL_SHAPE = (3, 3)
    EROSION_OPERATION_TYPE_STR = "erosion"
    PADDING_AMOUNT = 1
    PADDING_VALUE_FOR_EROSION_LIKE = 1  # Constant value for padding when operation_type is "erosion"
    PADDING_VALUE_FOR_DILATION_LIKE = 0 # Constant value for padding for other operation_types

    # --- Initialize structuring element if not provided ---
    if structuring_element is None:
        structuring_element = np.ones(DEFAULT_KERNEL_SHAPE)

    # --- Determine padding value and aggregation function based on operation type ---
    padding_constant_value: int
    aggregation_function: callable

    if operation_type == EROSION_OPERATION_TYPE_STR:
        padding_constant_value = PADDING_VALUE_FOR_EROSION_LIKE
        aggregation_function = np.max
    else:
        padding_constant_value = PADDING_VALUE_FOR_DILATION_LIKE
        aggregation_function = np.min

    # --- Calculate offsets for the structuring element's center ---
    # These offsets help in slicing the neighborhood correctly around the current pixel.
    center_x_offset = structuring_element.shape[0] // 2
    center_y_offset = structuring_element.shape[1] // 2

    # --- Prepare output and padded images ---
    output_image = np.zeros(input_image.shape, dtype=np.uint8)
    # Pad the input image to handle boundary conditions for the morphological operation.
    padded_image = np.pad(input_image, PADDING_AMOUNT, mode="constant", constant_values=padding_constant_value)

    # --- Apply the morphological operation ---
    # Iterate over the effective area of the padded image corresponding to the original image dimensions.
    # `row_idx` and `col_idx` represent the center of the structuring element in the padded image.
    for row_idx in range(center_x_offset, padded_image.shape[0] - center_x_offset):
        for col_idx in range(center_y_offset, padded_image.shape[1] - center_y_offset):
            # Extract the current neighborhood from the padded image.
            # The slice covers a region centered at (row_idx, col_idx) with dimensions of the structuring element.
            current_neighborhood = padded_image[row_idx - center_x_offset : row_idx + center_x_offset + 1,
                                                col_idx - center_y_offset : col_idx + center_y_offset + 1]

            # Apply the aggregation function only to elements covered by the structuring element (where kernel is 1).
            aggregated_value = aggregation_function(current_neighborhood[structuring_element == 1])

            # Assign the aggregated value to the corresponding pixel in the output image.
            # The indices for the output image are adjusted to map back from padded coordinates.
            output_image[row_idx - center_x_offset, col_idx - center_y_offset] = aggregated_value

    return output_image

def opening_filter(image: np.ndarray, structuring_element=None) -> np.ndarray:
    """
    Apply a morphological filter consisting of a dilation followed by an erosion.

    This operation effectively "fills in" small holes and connects disjoint areas.
    Note: A standard morphological 'opening' operation is typically defined as an erosion
    followed by a dilation. This function implements the reverse sequence:
    dilation followed by erosion, which is often referred to as a 'closing' operation.
    The function name 'opening_filter' is preserved as per constraints.

    Args:
        image:              The input image (e.g., a NumPy array) to which the filter
                            will be applied.
        structuring_element: The structuring element (kernel) used for both dilation
                            and erosion. If None, the underlying 'transform' function's
                            default structuring element will be used.

    Returns:
        The filtered image (NumPy array) after applying the dilation and then erosion.
    """
    # Constants for morphological operations, defined locally as per "return ONLY the
    # refactored code block" constraint and the few-shot example.
    MORPHOLOGICAL_DILATION_OPERATION = "dilation"
    MORPHOLOGICAL_EROSION_OPERATION = "erosion"

    # The original code's 'if kernel is None: np.ones((3, 3))' had no effect
    # on the 'kernel' variable being passed to 'transform' as the result
    # of np.ones was discarded. Therefore, this check is removed to simplify
    # logic while strictly preserving the observable behavior where 'transform'
    # receives 'None' if 'structuring_element' is not provided.

    # First, apply dilation to the image
    dilated_image = transform(image, MORPHOLOGICAL_DILATION_OPERATION, structuring_element)

    # Then, apply erosion to the dilated image
    result_image = transform(dilated_image, MORPHOLOGICAL_EROSION_OPERATION, structuring_element)

    return result_image

def closing_filter(img, kernel=None):
    """
    Applies a morphological closing filter to an image.

    A morphological closing operation consists of an erosion followed by a dilation.
    It is used to fill small holes and gaps in objects while preserving their shape
    and size, and can also smooth object boundaries. This operation is particularly
    effective at filling small holes and connecting nearby components.

    Args:
        img:    The input image. Expected to be a NumPy array-like structure.
        kernel: The structuring element (kernel) used for both erosion and dilation.
                Expected to be a NumPy array. If None, a default 3x3 square kernel
                of ones will be used.

    Returns:
        The morphologically closed image.
    """
    DEFAULT_SQUARE_KERNEL_SHAPE = (3, 3)
    OPERATION_EROSION = "erosion"
    OPERATION_DILATION = "dilation"

    if kernel is None:
        # `np` is assumed to be imported and available in the scope where
        # `closing_filter` is defined, as implied by the use of `np.ones`.
        kernel = np.ones(DEFAULT_SQUARE_KERNEL_SHAPE)

    # Perform erosion followed by dilation to achieve morphological closing.
    eroded_image = transform(img, OPERATION_EROSION, kernel)
    closed_image = transform(eroded_image, OPERATION_DILATION, kernel)
    return closed_image

import numpy as np


def binary_mask(gray: np.ndarray, mp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Generates two modified images by applying a binary pattern mask.

    Creates two copies of the input grayscale image:
    1. One where regions indicated by 'mp == 1' are set to 1.
    2. One where regions indicated by 'mp == 0' are set to 0.

    Args:
        gray: The input grayscale image or array.
        mp:   The pattern mask (e.g., a binary array) used to identify
              regions for modification. Pixels where mp is 1 are considered
              "foreground", and where mp is 0 are considered "background".

    Returns:
        tuple[numpy.ndarray, numpy.ndarray]: A tuple containing two modified images:
            - image_with_foreground_marked: A copy of the 'gray' image where
              pixels corresponding to `mp == 1` are set to 1.
            - image_with_background_cleared: A copy of the 'gray' image where
              pixels corresponding to `mp == 0` are set to 0.
    """
    image_with_foreground_marked = gray.copy()
    image_with_background_cleared = gray.copy()

    image_with_foreground_marked[mp == 1] = 1
    image_with_background_cleared[mp == 0] = 0

    return image_with_foreground_marked, image_with_background_cleared

def calculate_co_occurrence_matrix(grayscale_image: np.ndarray, offset_vector: tuple[int, int]) -> np.ndarray:
    """
    Calculates the Gray-Level Co-occurrence Matrix (GLCM) for an image.

    The GLCM quantifies the spatial relationship between pixels with specific gray levels.
    It counts the occurrences of pixel pairs with a certain value at a given spatial offset.

    Args:
        grayscale_image: A 2D NumPy array representing the grayscale image.
        offset_vector:   A tuple (dx, dy) specifying the spatial offset for co-occurrence.
                         dx and dy represent the horizontal and vertical displacements, respectively.

    Returns:
        A normalized 2D NumPy array representing the co-occurrence matrix.
        The matrix is normalized by the total number of counted pixel pairs.
    """
    # Determine the maximum pixel value in the image to set the dimensions of the GLCM.
    # The matrix dimensions will be (max_pixel_value + 1) x (max_pixel_value + 1).
    max_pixel_value = np.max(grayscale_image)
    co_occurrence_matrix = np.zeros([max_pixel_value + 1, max_pixel_value + 1], dtype=np.float64)

    offset_x, offset_y = offset_vector

    # Iterate over the image, excluding a 1-pixel border to ensure that
    # both the current pixel and its offset pixel are within image bounds.
    # The loops go from index 1 up to (shape - 2) for both dimensions.
    for row_idx in range(1, grayscale_image.shape[0] - 1):
        for col_idx in range(1, grayscale_image.shape[1] - 1):
            current_pixel_value = grayscale_image[row_idx, col_idx]
            offset_pixel_value = grayscale_image[row_idx + offset_x, col_idx + offset_y]
            co_occurrence_matrix[current_pixel_value, offset_pixel_value] += 1

    normalization_sum = np.sum(co_occurrence_matrix)

    # Prevent division by zero if no valid pixel pairs were found (e.g., for very small images
    # or offsets that place all potential pairs out of bounds).
    # If the sum is zero, dividing by 1 will result in an all-zero matrix, preserving behavior.
    if normalization_sum == 0:
        normalization_sum = 1

    # Normalize the co-occurrence matrix by the total number of counted pairs.
    return co_occurrence_matrix / normalization_sum

def haralick_descriptors(m: np.ndarray) -> list[float]:
    """
    Calculate a set of Haralick texture descriptors from a Gray-Level Co-occurrence Matrix (GLCM).

    This function computes 8 specific Haralick-like descriptors that quantify
    texture properties such as contrast, energy, correlation, and homogeneity.
    The input `m` is expected to be a normalized GLCM (sum of all elements equals 1)
    or a matrix where its elements represent probabilities.

    Args:
        m: The input Gray-Level Co-occurrence Matrix (GLCM) as a NumPy array.
           It should represent probabilities, typically a normalized GLCM.

    Returns:
        A list of 8 Haralick-like descriptor values in the following order:
        [
            Maximum Probability,
            Correlation,
            Energy (Angular Second Moment),
            Contrast,
            Dissimilarity,
            Inverse Difference Moment,
            Homogeneity,
            Entropy
        ]
    """
    # Create meshgrids for row and column indices
    row_indices, col_indices = np.ogrid[0:m.shape[0], 0:m.shape[1]]

    # Calculate common terms used in multiple descriptor formulas
    product_of_indices = row_indices * col_indices
    difference_of_indices = row_indices - col_indices

    # Calculate individual descriptor components
    max_probability_value = np.max(m)
    correlation_contribution_matrix = product_of_indices * m
    energy_contribution_matrix = m ** 2
    contrast_contribution_matrix = m * (difference_of_indices ** 2)
    dissimilarity_contribution_matrix = m * np.abs(difference_of_indices)
    inverse_difference_moment_contribution_matrix = m / (1 + np.abs(difference_of_indices))
    homogeneity_contribution_matrix = m / (1 + (difference_of_indices ** 2))

    # Calculate entropy elements, ensuring log is not applied to zero probabilities
    positive_probabilities = m[m > 0]
    entropy_elements = -(positive_probabilities * np.log(positive_probabilities))

    return [
        max_probability_value,
        correlation_contribution_matrix.sum(),
        energy_contribution_matrix.sum(),
        contrast_contribution_matrix.sum(),
        dissimilarity_contribution_matrix.sum(),
        inverse_difference_moment_contribution_matrix.sum(),
        homogeneity_contribution_matrix.sum(),
        entropy_elements.sum()
    ]

def calculate_haralick_descriptors_from_masks(image_masks: list[np.ndarray], offset: tuple[int, int]) -> np.ndarray:
    """
    Calculate Haralick texture descriptors for multiple image masks.

    This function iterates through a list of binary image masks, calculates
    the Grey-Level Co-occurrence Matrix (GLCM) for each mask using a specified
    offset, and then extracts Haralick texture descriptors from each GLCM.
    All calculated descriptors are concatenated into a single 1D NumPy array.

    Args:
        image_masks: An iterable of 2D NumPy arrays, where each array represents
                     a binary mask (e.g., a region of interest within an image).
        offset:      A 2-tuple of integers (dy, dx) representing the pixel
                     displacement (row and column offset) used for calculating
                     the co-occurrence matrix.

    Returns:
        A 1D NumPy array containing all Haralick descriptors concatenated
        from each input mask.
    """
    descriptor_arrays = [
        haralick_descriptors(matrix_concurrency(mask, offset))
        for mask in image_masks
    ]
    # Concatenate all individual descriptor arrays into a single 1D array.
    # `axis=None` flattens the result into a 1D array.
    return np.concatenate(descriptor_arrays, axis=None)

def euclidean(point1: np.ndarray, point2: np.ndarray) -> float:
    """
    Calculate the Euclidean distance between two n-dimensional points or vectors.

    The Euclidean distance (L2 distance) is the straight-line distance
    between two points in Euclidean space. It is calculated as the
    square root of the sum of the squared differences between the
    corresponding elements of the two input arrays.

    Args:
        point1: The first n-dimensional point or vector, expected as a NumPy array.
        point2: The second n-dimensional point or vector, expected as a NumPy array.
                Must have the same shape as `point1` for element-wise operations.

    Returns:
        The Euclidean distance between `point1` and `point2` as a float.
    """
    # Compute the squared differences, sum them, and take the square root.
    # The result is cast to a standard Python float.
    return float(np.sqrt(np.sum((point1 - point2) ** 2)))

import numpy as np
from scipy.spatial.distance import euclidean

def get_distances(descriptors: list[np.ndarray], base_descriptor_index: int) -> list[tuple[int, float]]:
    """
    Calculate Euclidean distances from a base descriptor to all other descriptors,
    normalize them, and return them sorted by distance in descending order.

    This function computes the Euclidean distance between a specified base descriptor
    and every other descriptor in the provided list. The resulting raw distances are
    then normalized to a maximum value of 1.0. The normalized distances are returned
    as a list of (original_index, normalized_distance) tuples, sorted from largest
    to smallest distance.

    Args:
        descriptors: A list or array-like collection of feature descriptors. Each descriptor
                     is expected to be a numerical array (e.g., numpy.ndarray)
                     from which Euclidean distances can be calculated.
        base_descriptor_index: The zero-based index of the descriptor within the 'descriptors'
                               list that will serve as the reference point for all distance
                               calculations.

    Returns:
        A list of tuples, where each tuple contains two elements:
        - The original index (int) of the descriptor in the input 'descriptors' list.
        - The normalized Euclidean distance (float) from the base descriptor to that descriptor.
        The list is sorted in descending order based on the normalized distance,
        meaning descriptors most distant from the base come first.
    """
    NORMALIZATION_TARGET_MAX_VALUE = 1.0

    # Retrieve the base descriptor for comparison
    base_descriptor = descriptors[base_descriptor_index]

    # Calculate Euclidean distance from the base_descriptor to every other descriptor
    raw_distances = [euclidean(current_descriptor, base_descriptor) for current_descriptor in descriptors]

    # Convert the list of raw distances to a NumPy array for efficient normalization
    distances_array = np.array(raw_distances)

    # Normalize the distances to a maximum value of NORMALIZATION_TARGET_MAX_VALUE (which is 1.0)
    # and then convert the resulting NumPy array back to a standard Python list.
    normalized_distances = normalize_array(distances_array, NORMALIZATION_TARGET_MAX_VALUE).tolist()

    # Pair each normalized distance with its original index using enumerate
    indexed_distances = list(enumerate(normalized_distances))

    # Sort the list of (index, distance) tuples by the distance value in descending order
    indexed_distances.sort(key=lambda item: item[1], reverse=True)

    return indexed_distances

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