def quick_sort(arr):
    """
    快速排序算法
    
    参数:
    arr: 要排序的列表
    
    返回:
    排序后的列表
    """
    # 基本情况：如果列表长度小于等于1，直接返回
    if len(arr) <= 1:
        return arr
    
    # 选择基准元素（这里选择中间元素）
    pivot = arr[len(arr) // 2]
    
    # 将元素分为三部分：小于基准、等于基准、大于基准
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    # 递归排序左右两部分，然后合并
    return quick_sort(left) + middle + quick_sort(right)


def quick_sort_in_place(arr, low=0, high=None):
    """
    原地快速排序算法（不创建新列表）
    
    参数:
    arr: 要排序的列表
    low: 起始索引
    high: 结束索引
    
    返回:
    原地排序后的列表
    """
    if high is None:
        high = len(arr) - 1
    
    if low < high:
        # 获取分区索引
        pi = partition(arr, low, high)
        
        # 递归排序分区前后的元素
        quick_sort_in_place(arr, low, pi - 1)
        quick_sort_in_place(arr, pi + 1, high)
    
    return arr


def partition(arr, low, high):
    """
    分区函数，用于原地快速排序
    
    参数:
    arr: 要排序的列表
    low: 起始索引
    high: 结束索引
    
    返回:
    基准元素的最终位置
    """
    # 选择最右边的元素作为基准
    pivot = arr[high]
    
    # 小于基准的元素的索引
    i = low - 1
    
    for j in range(low, high):
        # 如果当前元素小于或等于基准
        if arr[j] <= pivot:
            i += 1
            # 交换元素
            arr[i], arr[j] = arr[j], arr[i]
    
    # 将基准元素放到正确的位置
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def test_quick_sort():
    """测试快速排序算法"""
    print("测试快速排序算法")
    print("=" * 50)
    
    # 测试用例
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 2, 8, 1, 9, 3],
        [1, 2, 3, 4, 5],  # 已排序
        [5, 4, 3, 2, 1],  # 逆序
        [42],  # 单个元素
        [],  # 空列表
        [3, 3, 3, 3, 3],  # 所有元素相同
        [38, 27, 43, 3, 9, 82, 10]
    ]
    
    for i, test_arr in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test_arr}")
        
        # 复制列表用于原地排序测试
        arr_copy1 = test_arr.copy()
        arr_copy2 = test_arr.copy()
        
        # 使用普通快速排序
        sorted_arr = quick_sort(arr_copy1)
        print(f"普通快速排序结果: {sorted_arr}")
        
        # 使用原地快速排序
        sorted_in_place = quick_sort_in_place(arr_copy2)
        print(f"原地快速排序结果: {sorted_in_place}")
        
        # 验证排序结果是否正确
        expected = sorted(test_arr)
        if sorted_arr == expected and sorted_in_place == expected:
            print("✓ 排序正确")
        else:
            print("✗ 排序错误")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")


if __name__ == "__main__":
    # 运行测试
    test_quick_sort()
    
    # 示例使用
    print("\n\n示例使用:")
    print("-" * 30)
    
    # 示例1：普通快速排序
    numbers = [64, 34, 25, 12, 22, 11, 90]
    print(f"原始列表: {numbers}")
    sorted_numbers = quick_sort(numbers)
    print(f"排序后: {sorted_numbers}")
    
    # 示例2：原地快速排序
    numbers2 = [38, 27, 43, 3, 9, 82, 10]
    print(f"\n原始列表: {numbers2}")
    quick_sort_in_place(numbers2)
    print(f"原地排序后: {numbers2}")