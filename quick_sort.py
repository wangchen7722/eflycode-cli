#!/usr/bin/env python3
"""
快速排序算法实现
快速排序是一种高效的排序算法，平均时间复杂度为O(n log n)
"""

def quick_sort(arr):
    """
    快速排序主函数
    
    参数:
        arr: 要排序的列表
        
    返回:
        排序后的列表
    """
    # 如果列表长度小于等于1，直接返回
    if len(arr) <= 1:
        return arr
    
    # 选择基准元素（这里选择中间元素）
    pivot = arr[len(arr) // 2]
    
    # 将列表分为三部分：小于基准、等于基准、大于基准
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    # 递归排序左右两部分，然后合并
    return quick_sort(left) + middle + quick_sort(right)


def quick_sort_in_place(arr, low=0, high=None):
    """
    原地快速排序（节省内存空间）
    
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
        
        # 递归排序分区
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
        # 如果当前元素小于等于基准
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
        ([], []),  # 空列表
        ([1], [1]),  # 单个元素
        ([5, 2, 8, 1, 9], [1, 2, 5, 8, 9]),  # 普通列表
        ([9, 8, 7, 6, 5], [5, 6, 7, 8, 9]),  # 逆序列表
        ([3, 3, 3, 3], [3, 3, 3, 3]),  # 重复元素
        ([64, 34, 25, 12, 22, 11, 90], [11, 12, 22, 25, 34, 64, 90]),  # 更多元素
    ]
    
    # 测试标准快速排序
    print("1. 测试标准快速排序（非原地）:")
    for i, (input_arr, expected) in enumerate(test_cases):
        result = quick_sort(input_arr.copy())
        status = "✓" if result == expected else "✗"
        print(f"   测试用例 {i+1}: {status} 输入: {input_arr} -> 输出: {result}")
    
    print("\n2. 测试原地快速排序:")
    for i, (input_arr, expected) in enumerate(test_cases):
        arr_copy = input_arr.copy()
        result = quick_sort_in_place(arr_copy)
        status = "✓" if result == expected else "✗"
        print(f"   测试用例 {i+1}: {status} 输入: {input_arr} -> 输出: {result}")
    
    # 性能测试
    print("\n3. 性能测试:")
    import random
    import time
    
    # 生成随机列表
    random_list = [random.randint(1, 10000) for _ in range(1000)]
    
    # 测试标准快速排序性能
    start_time = time.time()
    sorted_list1 = quick_sort(random_list.copy())
    time1 = time.time() - start_time
    
    # 测试原地快速排序性能
    start_time = time.time()
    sorted_list2 = quick_sort_in_place(random_list.copy())
    time2 = time.time() - start_time
    
    # 验证排序结果
    is_sorted1 = all(sorted_list1[i] <= sorted_list1[i+1] for i in range(len(sorted_list1)-1))
    is_sorted2 = all(sorted_list2[i] <= sorted_list2[i+1] for i in range(len(sorted_list2)-1))
    
    print(f"   随机列表长度: 1000")
    print(f"   标准快速排序: {time1:.6f} 秒, 排序正确: {'✓' if is_sorted1 else '✗'}")
    print(f"   原地快速排序: {time2:.6f} 秒, 排序正确: {'✓' if is_sorted2 else '✗'}")
    
    print("\n" + "=" * 50)
    print("快速排序算法实现完成！")


if __name__ == "__main__":
    test_quick_sort()